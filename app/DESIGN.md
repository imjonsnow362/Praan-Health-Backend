# DESIGN.md

## 1. Database Decision

### **Current Implementation: SQLite**
* **Choice:** We used **SQLite** for this prototype.
* **Why:** It requires no setup, runs locally on a single file (`praan_health.db`), and is sufficient for single-user development testing.
* **Tradeoff:** It lacks concurrency (locks on writes) and advanced features like connection pooling, but allows for rapid iteration without Docker containers.

### **Production Plan: PostgreSQL**
* **Why SQL?** The data model is strictly relational:
    * `Users` own `Members`.
    * `Members` have one active `CareProgram`.
    * `CarePrograms` have many `DailyLogs`.
* **Specific Tradeoff:** SQL ensures data integrity (ACID) so orphaned health logs cannot exist. NoSQL was rejected because "Adherence Calculation" requires complex joins across these related tables, which is inefficient in document stores.

---

## 2. Caching Architecture

### **Current Implementation: In-Memory (TTLCache)**
We implemented Application-Level Caching in `app/api/v1/logs.py` using the `cachetools` library.

* **Strategy:** Write-Through / Invalidation.
* **What is Cached:** The Adherence Score (`GET /adherence/{program_id}`).
* **Why:** Adherence calculation involves scanning `DailyLog` history and comparing against `ProgramConfig`. Caching this reduces DB load on the Dashboard view.
* **TTL (Time To Live):** 60 seconds.
* **Invalidation Trigger:** When a new log is created (`POST /logs`), the specific cache key for that program is deleted immediately. This ensures the user sees their new score instantly upon logging.

### **Code Reference**
The implementation uses `TTLCache(maxsize=100, ttl=60)` to store results in server memory.

---

## 3. Security Implementation

### **Current Implementation**
* **Authentication:** Header-based mechanism using `X-User-ID`.
* **Access Control (RBAC):** We created a shared dependency `get_current_user` in `app/api/deps.py`.
* **Permission Boundaries:** Every CRUD endpoint verifies ownership.
    * *Example:* In `enroll_member`, we explicitly check `db.query(Member).filter(id=member_id, user_id=user_id)` before allowing the action. This prevents User A from enrolling or modifying User B's family members.
* **Input Validation:** Pydantic schemas (`EnrollmentRequest`, `LogCreate`) strictly define allowed fields, preventing injection attacks.

### **Production Gap (What's Missing)**
* The current `X-User-ID` header is not secure for production. In a real deployment, this would be replaced by **OAuth2 (JWT Tokens)** verified against an Identity Provider (like Auth0 or Firebase).
* We are storing passwords as plain text for the prototype. Production must use `bcrypt` hashing.

---

## 4. Scalability Plan (100K Families)

*Note: This section outlines the theoretical plan for scale, as the current prototype runs locally.*

### **What Would Break First?**
* **Synchronous Processing:** Currently, `POST /meals/analyze` waits for the AI (mocked) to finish. With 100k users, 5,000 concurrent uploads would starve the API threads, causing timeouts.
* **SQLite Locks:** SQLite allows only one writer at a time. High traffic would cause "Database Locked" errors.

### **Scaling Strategy**
1.  **Async Workers:** Move `MockAIService` logic to a background queue (Celery/RabbitMQ). The API would return "202 Accepted" immediately, and the client would poll for results.
2.  **Read Replicas:** Deploy PostgreSQL with 1 Primary (Writes) and 3 Replicas (Reads). Point all Dashboard `GET` requests to the replicas.
3.  **CDN:** Serve uploaded meal photos via CloudFront/CDN to offload bandwidth from the API servers.

---

## 5. Known Limitations & Shortcuts

1.  **Mock AI:** The system returns hardcoded nutrition data ("Grilled Chicken") instead of calling a real Vision API.
2.  **Local Storage:** Images are saved to the local `uploads/` folder. This is not stateless and would fail on cloud platforms like Heroku/AWS Lambda.
3.  **Manual Timestamping:** We manually set `datetime.now()` in Python to handle SQLite constraints, rather than relying on database server time.

---

## 6. Production Readiness Checklist

To move this code to production, we would need:
1.  [ ] **Dockerization:** Containerize the FastAPI app.
2.  [ ] **Cloud Storage:** Replace local file writes with **AWS S3** boto3 calls.
3.  [ ] **Testing:** Add Pytest unit tests for the adherence logic.
4.  [ ] **Environment Variables:** Move `API_URL` and DB credentials to `.env` files.