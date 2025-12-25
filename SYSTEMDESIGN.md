# System Design Doc: Praan Family Health OS

| **Author** | Akshat Bhatawdekar |
| :--- | :--- |
| **Status** | Ready for Review|
| **Approvers** | [Srishti/CTO] |
| **Last Updated** | 24th December 2025 |

## 1. Context & Scope

### **Why are we building this?**
Praan aims to be the operating system for family health. Currently, managing health data for multiple family members (e.g., aging parents) is fragmented across WhatsApp chats, paper files, and disparate apps. We need a centralized platform where a "Family Manager" can track nutrition, strength training, and clinical metrics for their dependents.

### **In Scope**
* Multi-tenant architecture (Users managing Members).
* 90-Day Care Program engine with configurable goals.
* Logging system for Nutrition, Workouts, and Vitals.
* Basic AI integration for meal analysis (Mocked for MVP).
* Adherence calculation engine.

### **Out of Scope (for now)**
* Real-time chat with doctors.
* Wearable device integration (Apple Health/Fitbit).
* Billing/Subscription management.

---

## 2. Architecture & System Overview
### 2.1 High-Level Architecture
We chose a **Layered Service-Oriented Architecture** (modular monolith). This allows us to move fast now (single repo, shared logic) while keeping clear boundaries so we can split the "AI Processing" or "Analytics" into microservices when we hit 100k+ users.

![Image of High Level System Architecture Diagram](./Angular%20FastAPI%20Image-2025-12-24-202146.png)

### 2.2 Component Interaction Flow
**Scenario: Meal Photo Upload & Processing**

1.  **Presigned URL:** Client requests upload permission. API generates a secure AWS S3 Presigned URL.
2.  **Direct Upload:** Client uploads image directly to S3 (Reducing load on backend servers).
3.  **Metadata Sync:** Client sends `image_key` to API.
4.  **Async Handoff:** API creates a `DailyLog` record (Status: `PROCESSING`) and pushes a task to **Celery/Redis**. API returns `202 Accepted` to user.
5.  **Processing:** Worker pulls task -> Downloads image -> Runs AI Inference -> Extracts Macros.
6.  **Completion:** Worker updates `DailyLog` (Status: `COMPLETED`) -> Triggers Adherence Recalculation -> **Invalidates Redis Cache**.

### 2.3 Technology Choices and rationale

* **Language: Python (FastAPI):** Selected for high performance (AsyncIO), native Pydantic integration for strict data validation (critical for health data), and rich ecosystem for AI/ML libraries.
* **Database: PostgreSQL:** Chosen over NoSQL (see Section 2.1).
* **Caching: Redis:** Low latency, supports complex data structures (Sorted Sets for Leaderboards), and Pub/Sub.
* **Task Queue: Celery:** Robust, industry-standard for handling background jobs in Python.

### 2.4 Database choice

**Justification & Tradeoffs:**

* **Rapid Development (Current - SQLite):**
    * **Simplicity:** Currently utilizing `sqlite:///./praan_health.db` to prioritize iteration speed. It requires no server overhead and runs as a single file, which is ideal for the prototyping phase.
    * **ORM Abstraction:** Using SQLAlchemy allows us to define models now that will work with PostgreSQL later with minimal refactoring.

* **Relational Integrity (Production Requirement - PostgreSQL):**
    * **Winner:** The domain is strictly hierarchical (`User` -> `Member` -> `Program` -> `Logs`). Deleting a user must cascade strictly to members and logs. PostgreSQL handles these constraints more robustly in concurrent environments.

* **Consistency (Production Requirement - PostgreSQL):**
    * **Winner:** Health data (PHI) requires strict ACID compliance. We cannot risk "eventual consistency" where a clinical check-in is lost. PostgreSQL ensures data validity across multiple concurrent server connections better than SQLite.

* **Complex Aggregation (Production Requirement - PostgreSQL):**
    * **Winner:** Adherence reporting requires joining 4+ tables. PostgreSQL's query optimizer is significantly more performant for these complex `JOIN` operations than SQLite at scale.

* **Flexibility (Production Requirement - PostgreSQL):**
    * **Mitigation:** We intend to use Postgres `JSONB` for the `payload` column. This allows us to store and *efficiently query* unstructured data (Meal Macros vs. Workout Reps) within a structured schema, a feature SQLite supports only partially via extensions.

---

## 3. Data Model Design

### 3.1 Schema Design
We utilize a relational schema with a hybrid approach (Structured Relations + JSONB) to handle the variability of health data.

#### **A. Core Entities**
* **Users (`users`):**
    * `id` (PK), `email` (Unique), `password_hash`, `full_name`, `created_at`.
    * *Purpose:* Authentication and billing root.
* **Members (`members`):**
    * `id` (PK), `user_id` (FK), `name`, `age`, `relation_type`, `deleted_at` (Soft Delete).
    * *Purpose:* The patient profiles managed by the User.
* **Care Programs (`care_programs`):**
    * `id` (PK), `member_id` (FK), `title`, `start_date`, `end_date`, `status` (`ACTIVE`, `PAUSED`, `COMPLETED`), `phase` (1-3).
    * *Purpose:* The 90-day container for health tracking.
* **Program Components (`program_configs`):**
    * `id` (PK), `program_id` (FK), `nutrition_goals` (JSONB), `strength_goals` (JSONB), `clinical_goals` (JSONB).
    * *Purpose:* Stores the "Configurable Expectations" (e.g., Target Protein: 60g) without needing schema migrations for new goal types.

#### **B. Health Data (Time-Series)**
* **Daily Logs (`daily_logs`):**
    * `id` (PK), `program_id` (FK), `timestamp` (Index), `log_type` (`NUTRITION`, `WORKOUT`, `CHECKIN`), `is_verified` (Boolean).
    * `payload` (JSONB): Stores the variable data (e.g., `{ "calories": 500, "macros": {...} }` vs `{ "systolic": 120, "diastolic": 80 }`).
    * *Partitioning:* Partitioned by `RANGE (timestamp)` (Monthly partitions).

#### **C. Derived Data**
* **Adherence Metrics (`adherence_metrics`):**
    * `id` (PK), `program_id` (FK), `date`, `nutrition_score` (Float), `strength_score` (Float), `total_score` (Float), `details` (JSONB).
    * *Purpose:* Pre-calculated summaries to make Dashboard reads instant (O(1)) instead of aggregating logs on the fly (O(N)).

#### **D. Image Metadata**
* **Image Logs (`image_metadata` - optional or integrated into logs):**
    * `id` (PK), `log_id` (FK), `s3_key` (Path), `upload_timestamp`, `processing_status` (`PENDING`, `COMPLETED`, `FAILED`), `extracted_data` (JSONB snapshot).
    * *Purpose:* Tracks the lifecycle of an uploaded meal photo from raw upload to AI extraction.

#### **E. Audit Trails**
* **Audit Log (`audit_logs`):**
    * `id` (PK), `actor_id` (User ID), `resource_type` (e.g., 'Member'), `resource_id`, `action` (e.g., 'DELETE'), `ip_address`, `timestamp`.
    * *Purpose:* Security & Compliance (HIPAA requirement to track access).


### 3.2 Critical Design Questions

#### **Q1: How do you model time-series health data efficiently?**
* **Strategy:** **Database Partitioning**.
* **Implementation:** The `daily_logs` table is partitioned by month.
* **Why:**
    * **Query Speed:** 90% of queries request the "Current Week" or "Last 30 Days." The database engine only scans the relevant partition (e.g., `logs_2025_12`), ignoring millions of older rows.
    * **Index Size:** Smaller indexes per partition fit entirely in RAM, preventing disk thrashing.

#### **Q2: How do you prevent race conditions (Concurrent Logging)?**
* **Scenario:** Two siblings log a meal for the same parent at the exact same moment.
* **Strategy:**
    * **Insert-Only Logs:** The `daily_logs` table is append-only. Inserts generally do not block each other.
    * **Atomic Aggregation:** For updating the `AdherenceMetrics` score, we use **Atomic Updates** rather than "Read-Modify-Write."
        * *Bad:* `score = read(); save(score + 5)` (Race condition risk).
        * *Good:* `UPDATE metrics SET total_score = total_score + 5 WHERE id = X` (Database handles locking).

#### **Q3: How do you handle Soft Deletes vs Hard Deletes?**
* **Soft Deletes (User Actions):**
    * All core tables (`members`, `programs`) have a `deleted_at` timestamp.
    * API queries filter `WHERE deleted_at IS NULL`.
    * *Reason:* Prevents accidental data loss and allows "Undo" functionality.
* **Hard Deletes (Compliance):**
    * A scheduled background job (Cron) runs nightly.
    * It permanently deletes records where `deleted_at > 30 days`.
    * *Reason:* Compliance with GDPR/HIPAA "Right to be Forgotten" mandates.

#### **Q4: Strategy for Data Retention and Archival?**
* **Hot Storage (Operational DB):** Data from the last **2 Years**. Stored on high-performance SSDs (AWS RDS GP3).
* **Cold Storage (Archival):** Data older than 2 years is moved to **AWS S3 (Parquet format)** or **Glacier**.
* **Process:** An ETL job runs monthly to archive old partitions and drop them from the primary database, keeping the active dataset lean and performant.

---

## 4. Caching Strategy

### 4.1 Caching Design
* **Technology:** Redis (Cluster mode for production).
* **Eviction Policy:** `volatile-lru` (Evict least recently used keys with an expiry set).

### 4.2 What to Cache
* **User Profiles & Configs:** Read often, change rarely. (TTL: 1 hour).
* **Adherence Summaries:** Expensive to calculate on every page load. (TTL: Until Invalidated).
* **NEVER Cache:** Raw PHI (unless encrypted), Real-time clinical alerts.

### 4.3 Where to Cache

We employ a multi-level caching approach to optimize performance at different stages of the request lifecycle.

1.  **Application-Level Caching (In-Memory)**
    * **Technology:** Python `cachetools` (TTLCache).
    * **Usage:** Used in the current prototype for storing **Adherence Scores** (TTL: 60s).
    * **Pros/Cons:** Extremely fast (nanosecond latency) but local to the specific container instance. If the container restarts, cache is lost. Not suitable for sharing state across horizontal replicas.

2.  **Distributed Caching (Production Primary)**
    * **Technology:** **Redis** (Cluster Mode).
    * **Usage:** The single source of truth for cached data across all API worker nodes. Stores **Session Tokens**, **Rate Limiting Counters**, and **Adherence Summaries**.
    * **Why:** Ensures that if User Request A hits Server 1 and Request B hits Server 2, they both see the same cached adherence score.

3.  **CDN (Content Delivery Network)**
    * **Technology:** **AWS CloudFront**.
    * **Usage:** Caching static assets (Frontend JS/CSS bundles) and **Meal Photos** uploaded to S3.
    * **Why:** Offloads bandwidth from our backend servers and serves images from edge locations closer to the user, significantly speeding up the "Gallery" view in the dashboard.

4.  **Database Query Caching**
    * **Technology:** PostgreSQL Shared Buffers & OS Page Cache.
    * **Usage:** Automatic caching of frequently accessed index pages (e.g., the B-Tree index for `DailyLogs` timestamps).
    * **Optimization:** We tune the `shared_buffers` configuration in Postgres to keep the "Active Working Set" (logs from the last 7 days) in RAM, preventing expensive disk I/O.

### 4.4 Specific Scenarios
**Scenario: 100k Users Uploading Simultaneously (Thundering Herd)**
* **Handling:** The API does **not** process synchronously. It creates a lightweight "Job ID" and returns.
* **Queueing:** The load moves to the Redis Broker. We scale **Worker Nodes** horizontally (Kubernetes HPA) based on Queue Depth, not API CPU.

**Scenario: Invalidation (Write-Through)**
* **Event:** User uploads meal -> AI updates DB.
* **Action:** The Worker performs a `DEL program:{id}:adherence`.
* **Result:** The next time the user loads the dashboard, the API finds a **Cache Miss**, recalculates the fresh score from the DB, and repopulates Redis.

**Scenario: Stale Data Tolerance**
* **Strict Real-time:** Clinical Vitals (BP, Heart Rate). fetched directly from DB.
* **Stale Tolerated:** "Weekly Leaderboard" or "Monthly Trends" can be cached for 5-15 minutes.

---
## 5. API Design

### 5.1 Production Considerations
* **Rate Limiting:** Leaky Bucket algorithm via Redis. Limit: 100 req/min per User (prevent abuse).
* **Pagination:** Cursor-based pagination for `DailyLogs` (better for infinite scroll/time-series than offset-based).
* **Versioning:** URI Versioning (`/api/v1/...`) to allow breaking changes without disrupting older mobile clients.

### 5.2 Core Endpoints Examples

**1. Log Health Data**
* **POST** `/api/v1/logs`
* **Headers:** `Authorization: Bearer <token>`, `X-Request-ID: <uuid>`
* **Rate Limit:** 60/min
* **Request:**
    ```json
    { "program_id": 101, "log_type": "NUTRITION", "payload": { "calories": 500 } }
    ```
* **Response (201 Created):**
    ```json
    { "id": 555, "status": "VERIFIED", "adherence_impact": "+5 points" }
    ```

**2. Get Program History (Paginated)**
* **GET** `/api/v1/programs/{id}/history?limit=20&cursor=MzAyMg==`
* **Response (200 OK):**
    ```json
    {
      "data": [ ... logs ... ],
      "pagination": { "next_cursor": "NzkxMA==", "has_more": true }
    }
    ```

**3. Error Handling**
* **400 Bad Request:** Validation Error (e.g., negative calories).
* **401 Unauthorized:** Missing/Expired Token.
* **403 Forbidden:** Accessing a Member profile you don't own (Resource Ownership Check).
* **429 Too Many Requests:** Rate limit exceeded (`Retry-After: 30`).

---

## 5. Security Architecture

### 5.1 Authentication & Authorization
* **Authentication Mechanism:**
    * **Primary:** OAuth 2.0 / OpenID Connect (integration with Google/Apple Sign-in).
    * **Implementation:** We exchange IdP tokens for our own secure, short-lived **JWTs** (JSON Web Tokens). This avoids storing passwords directly in our database.
* **RBAC Model (Role-Based Access Control):**
    * `FAMILY_MANAGER`: Full Read/Write access to owned members and programs.
    * `MEMBER`: (Future) Read-only access to their own data via a patient portal.
    * `DOCTOR`: (Future) Scoped access to specific clinical logs for a specific time window.
* **Family Member Permission Boundaries:**
    * Strict logical isolation. A `FAMILY_MANAGER` can *only* create/edit members where `member.user_id == current_user.id`.

### 5.2 Data Protection & Encryption
* **Encryption at Rest:**
    * **Database:** AWS RDS Encrypted Storage (AES-256).
    * **Object Storage:** S3 Server-Side Encryption (SSE-S3).
* **Encryption in Transit:**
    * TLS 1.3 forced for all API communication.
    * HSTS (HTTP Strict Transport Security) enabled to prevent downgrade attacks.
* **Image Storage Security:**
    * S3 Buckets are configured as **Private** (Block Public Access: On).
    * **Access Control:** The API generates **Presigned URLs** (TTL: 5 minutes) for the frontend. This ensures only authenticated users with a valid session can view family photos; they cannot be scraped publicly.

### 5.3 Access Control Implementation
* **Preventing Member A from accessing Member B:**
    * **Middleware Strategy:** We implement a centralized authorization dependency.
    * **Logic:** `SELECT 1 FROM members WHERE id = {target_member_id} AND user_id = {current_requester_id}`. If the result is empty, return `403 Forbidden`.
* **Audit Logging:**
    * **Requirement:** HIPAA compliance requires tracking "Who accessed what, when."
    * **Implementation:** An async middleware logs every "Write" operation (POST/PUT/DELETE) to an immutable `audit_logs` table.
    * **Schema:** `id`, `actor_id`, `resource_type` (e.g., DailyLog), `resource_id`, `action` (e.g., UPDATE), `ip_address`, `timestamp`.

### 5.4 API Security
* **API Key Management:**
    * Keys for AI services (e.g., OpenAI, Google Vision) are stored in **AWS Secrets Manager** or HashiCorp Vault, injected as environment variables at runtime. Never committed to code.
* **Rate Limiting:**
    * **Strategy:** Leaky Bucket algorithm implemented via Redis.
    * **Policy:** 100 requests per minute per `user_id`.
    * **Purpose:** Prevents brute-force attacks and abuse of the expensive AI inference endpoint.


---

## 6. Scalability & Performance

### 6.1 Database Scalability
* **Read Replicas Strategy:**
    * Family health apps are **Read-Heavy** (80% reads, 20% writes).
    * **Configuration:** 1 Primary Node (Writes) + 3 Read Replicas.
    * **Routing:** The API layer automatically routes `GET` requests to replicas and `POST/PUT` to the primary.
* **Vertical vs. Horizontal Scaling:**
    * **0 - 10k Users:** Vertical Scaling. Upgrade the Primary RDS instance size (e.g., db.t3.medium -> db.m5.large).
    * **100k+ Users:** Horizontal Scaling (Sharding).
        * **Strategy:** **Sharding by User ID**. Since family data is isolated (User A's data never interacts with User B's), we can split users across multiple database physical shards. This allows infinite horizontal scale.

### 6.2 Handling Concurrency
* **10k Concurrent Users:**
    * **Load Balancer:** AWS ALB distributes traffic across 5-10 API Container instances.
    * **DB:** Connection Pooling (PgBouncer) is essential to prevent exhausting database connections.
* **100k Concurrent Users:**
    * **Async Architecture:** Crucial here. Image uploads are offloaded to S3 + Celery immediately.
    * **Caching:** Aggressive caching of the "Dashboard View" in Redis reduces DB hits by ~90%.
    * **CDN:** Static assets (JS/CSS) and Profile Images served via CloudFront.

### 6.3 Performance Targets & SLAs
* **API Response Time:**
    * **Reads (Cached):** < 50ms.
    * **Reads (Uncached):** < 200ms (p95).
    * **Writes:** < 300ms.
* **Cache Hit Rates:** Target > 85% for Adherence/Dashboard endpoints.
* **AI Processing:**
    * **Expectation:** < 5 seconds per image.
    * **SLA:** 99.9% of images processed within 10 seconds.
* **Database Query Performance:**
    * **Cost Optimization:** All queries must use indexes. No full table scans allowed on `DailyLogs`.
    * **Partitioning:** `DailyLogs` table partitioned by month to keep index size manageable and query cost low.
