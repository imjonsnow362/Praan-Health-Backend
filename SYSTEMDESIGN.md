# Praan Family Health OS - System Design Document

## 1. Architecture & System Overview

### 1.1 High-Level Architecture
The system adopts a **Layered Service-Oriented Architecture (SOA)** designed for scalability, security, and separation of concerns. While the prototype is a modular monolith (FastAPI), the boundaries allow for easy extraction into microservices (e.g., an independent "AI Processing Service") as the system scales to 100k+ users.

**Core Components:**
1.  **Client Layer:** Web App (Angular).
2.  **API Gateway / Backend:** FastAPI (Python) server handling request orchestration, authentication, and validation.
3.  **Data Layer:**
    * **Primary DB (PostgreSQL):** Relational data (Users, Programs, Configs, Logs).
    * **Cache (Redis):** Hot data (Session tokens, Adherence Summaries, Rate Limits).
    * **Object Storage (AWS S3):** Raw meal photos and clinical reports.
4.  **Async Worker Layer:** Celery + Redis Broker for heavy lifting (AI Image Analysis, Weekly Report Generation).



### 1.2 Component Interaction Flows
**Scenario: Meal Upload & Adherence Calculation**
1.  **Client** requests a pre-signed URL from **API**.
2.  **Client** uploads image directly to **Object Storage (S3)** to save backend bandwidth.
3.  **Client** sends metadata (S3 key) to **API**.
4.  **API** saves `DailyLog` (status: `PROCESSING`) to **DB** and pushes a task to **Celery Queue**.
5.  **Worker** picks up task, calls **AI Vision Model**, extracts macros, updates **DB**, and invalidates **Redis Cache**.
6.  **Client** receives notification via WebSocket or polling that analysis is complete.

### 1.3 Technology Choices & Rationale
* **Language: Python (FastAPI):** Selected for high performance (AsyncIO), native Pydantic integration for strict data validation (critical for health data), and rich ecosystem for AI/ML libraries.
* **Database: PostgreSQL:** Chosen over NoSQL (see Section 2.1).
* **Caching: Redis:** Low latency, supports complex data structures (Sorted Sets for Leaderboards), and Pub/Sub.
* **Task Queue: Celery:** Robust, industry-standard for handling background jobs in Python.

---

## 2. Database Design & Data Model

### 2.1 Database Choice: SQL (PostgreSQL) vs NoSQL
**Decision:** **SQL (PostgreSQL)**.
**Justification:**
1.  **Relational Integrity:** The domain is strictly hierarchical: `User` -> `Member` -> `CareProgram`. Deleting a Member must cascade delete their data. SQL handles this natively.
2.  **ACID Compliance:** Health data (PHI) requires strict consistency. We cannot afford "eventual consistency" where a doctor sees a different blood pressure reading than the patient.
3.  **Complex Aggregation:** Generating "Adherence Reports" requires joining logs, configs, and programs across time ranges. SQL `JOIN` and `GROUP BY` operations are more performant and rigid than NoSQL aggregation pipelines for this specific use case.
4.  **Hybrid Flexibility:** We utilize PostgreSQL's `JSONB` column type for the `payload` field in `DailyLogs`. This gives us NoSQL-like flexibility for varying health data types (e.g., Yoga has "duration", Weightlifting has "sets/reps") while maintaining Relational integrity for the user links.

### 2.2 Core Entities (Schema Design)
* **Users:** `id`, `email`, `password_hash`, `role`, `created_at`.
* **Members:** `id`, `user_id` (FK), `name`, `relation_type`, `dob`.
* **CarePrograms:** `id`, `member_id` (FK), `title`, `start_date`, `end_date` (90 days), `status` (`ACTIVE`, `COMPLETED`), `phase`.
* **ProgramConfigs:** `id`, `program_id` (FK), `nutrition_goals` (JSONB), `strength_goals` (JSONB).
* **DailyLogs:** `id`, `program_id` (FK), `log_type` (`NUTRITION`, `WORKOUT`), `payload` (JSONB), `timestamp`, `is_verified`.
* **AdherenceMetrics:** `id`, `program_id` (FK), `date`, `total_score`, `details` (JSONB). *Derived Data Table for fast reads.*

### 2.3 Critical Design Questions

**Q: How do you model time-series health data efficiently?**
* **Strategy:** **TimescaleDB (PostgreSQL Extension)** or Native Partitioning.
* **Implementation:** We partition the `DailyLogs` table by `month`. Queries usually request "current week" or "last 90 days." Partitioning keeps index sizes small and queries fast. Old partitions (e.g., > 2 years) can be moved to cold storage (S3/Glacier).

**Q: Prevention of Race Conditions?**
* **Scenario:** Two family members log a meal for "Grandpa" at the exact same time.
* **Strategy:** **Optimistic Locking** or Atomic Updates.
* The `DailyLog` table is append-only, so race conditions are rare there. For `AdherenceMetrics` (which aggregates scores), we use atomic database transactions (`UPDATE metrics SET score = score + 5 WHERE id = X`).

**Q: Soft Deletes vs Hard Deletes (PHI)?**
* **Strategy:** **Soft Deletes** (`deleted_at` timestamp).
* **Rationale:** Accidental deletion by a user is common. We filter `WHERE deleted_at IS NULL` in API queries.
* **Hard Delete (GDPR/HIPAA):** A nightly cron job permanently purges records where `deleted_at > 30 days` to comply with "Right to be Forgotten" laws.

**Q: Data Retention & Archival?**
* **Active Data:** Last 2 years stored in hot Postgres storage.
* **Archival:** Data > 2 years is ETL'd to a Data Warehouse (BigQuery/Snowflake) for population health analytics and deleted from the operational DB to maintain performance.

---

## 3. Caching Strategy

### 3.1 Caching Layer Design
This is critical for reducing DB load on read-heavy dashboards.

* **What to Cache:**
    * **User Profiles & Program Configs:** High read/write ratio (Changed rarely, read often).
    * **Aggregated Summaries (Adherence):** Expensive to compute (requires scanning 7 days of logs).
* **What NEVER to Cache:** Real-time clinical alerts, Raw PHI (unless encrypted), Search results.
* **Granularity:** Entire Objects for User Profiles; Field-level for Adherence scores.

### 3.2 Invalidation Strategy (Event-Driven)
**Scenario:** User uploads meal photo -> AI extracts nutrition -> Adherence Recalculated.
1.  **Write:** New `DailyLog` committed to DB.
2.  **Invalidate:** Backend publishes event `log_created`.
3.  **Action:** Cache Key `program:{id}:adherence:today` is **Deleted** (Write-through or Cache-aside).
4.  **Next Read:** API finds cache miss, computes fresh score from DB, and re-populates cache.

### 3.3 Handling 100k Simultaneous Uploads (Thundering Herd)
* **Strategy:** **Async Processing Queue**.
* The API does *not* process images synchronously. It accepts the file, returns `202 Accepted`, and offloads processing to Celery/Kafka. This keeps the API responsive (< 100ms) even if the AI processing queue backs up to 10 minutes.

### 3.4 Stale Data Tolerance
* **Real-time Required:** Clinical alerts (High BP), Verification status.
* **Stale Tolerated (1-5 mins):** "Weekly Progress" dashboard, Leaderboards.

---

## 4. API Design

### 4.1 Production Considerations
* **Rate Limiting:** Leaky Bucket algorithm via Redis. Limit: 100 req/min per User (prevent abuse).
* **Pagination:** Cursor-based pagination for `DailyLogs` (better for infinite scroll/time-series than offset-based).
* **Versioning:** URI Versioning (`/api/v1/...`) to allow breaking changes without disrupting older mobile clients.

### 4.2 Core Endpoints Examples

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
* **Auth Mechanism:** OAuth 2.0 / OpenID Connect (integration with Google/Apple Sign-in).
* **RBAC Model:**
    * **Role: FAMILY_MANAGER:** Full CRUD on owned Members.
    * **Role: READ_ONLY:** (Optional) For doctor access.
* **Permission Boundaries:** Middleware intercepts every request. It checks: `SELECT 1 FROM members WHERE id = {target_id} AND user_id = {current_user_id}`. If 0 rows, return 403.

### 5.2 Data Protection
* **Encryption at Rest:** AES-256 for Database volumes and S3 Buckets.
* **Encryption in Transit:** TLS 1.3 only for all API communication.
* **Image Security:**
    * Images stored in private S3 buckets (No public access).
    * API generates **Pre-signed URLs** (valid for 5 mins) for the frontend to render images. This prevents public scraping.

### 5.3 Audit Logging
* **Requirement:** "Who accessed what, when?"
* **Implementation:** Middleware logs every "Write" operation (POST/PUT/DELETE) to a separate immutable `audit_logs` table.
* **Schema:** `actor_id`, `target_resource`, `action`, `timestamp`, `ip_address`.

---

## 6. Scalability & Performance

### 6.1 Database Scalability
* **Read Replicas:** 80% of traffic is "Reads" (Viewing Dashboard). We deploy 1 Primary (Write) and 3 Replicas (Read). API routes GET requests to Replicas.
* **Vertical Scaling:** Upgrade Primary instance size (CPU/RAM) up to 10k users.
* **Horizontal Scaling:** At 100k+ users, implement **Sharding** based on `user_id`. Since family data is isolated per user, sharding by user ID is highly effective.

### 6.2 Performance Targets
* **API Response Time:** < 200ms (p95).
* **Cache Hit Rate:** > 85%.
* **AI Processing:** < 5 seconds.
* **DB Query Cost:** Optimized via Composite Indexes (e.g., `CREATE INDEX idx_logs_program_date ON daily_logs (program_id, timestamp DESC)`).