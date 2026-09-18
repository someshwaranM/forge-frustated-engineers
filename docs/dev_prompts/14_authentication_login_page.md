# Vigil --- Phase 14 Dev Prompt: Authentication & Login Page

`docs/dev_prompts/14_authentication_login_page.md`

*(Scope: implement full-stack authentication for Vigil with a dedicated
MySQL `users` table, secure JWT-based authentication endpoints, a
polished Login page, protected routes, session persistence, and user
profile/logout functionality.)*

------------------------------------------------------------------------

## Purpose

Phase 14 introduces authentication to the Vigil application.

The objective is to ensure that:

-   Unauthenticated users can access only `/login`.
-   Authenticated users can access the Vigil application.
-   Authentication state survives browser refreshes.
-   The backend validates credentials and issues JWT bearer tokens.
-   The frontend validates the stored token through `/api/auth/me` on
    startup.
-   Case/dashboard/call/chat APIs automatically receive the
    authenticated token.
-   The Topbar and Sidebar display the authenticated user's profile.
-   Logout clears the client authentication state and returns the user
    to `/login`.

This phase adds authentication around the existing Vigil application. Do
not redesign existing application pages or change the existing
compliance workflow.

------------------------------------------------------------------------

## User Review Required

> \[!IMPORTANT\] **Initial Demo User**
>
> -   **Username:** `admin`
> -   **Password:** `admin12345`
> -   **Role:** `Audit Officer`
> -   **Team:** `Compliance`
> -   **Email:** `audit.officer@vigil.com`
> -   **Access:** `All`
>
> The password MUST be stored only as a salted bcrypt hash. Never store
> or return the plaintext password.

> \[!NOTE\] The demo credentials are intended for the local/demo Vigil
> environment. Do not hardcode the plaintext password into backend
> authentication logic or database queries.

> \[!TIP\] Add a **Fill Demo Credentials** action on the Login page for
> fast hackathon/demo testing. The button may populate the login form,
> but it must not bypass authentication.

------------------------------------------------------------------------

# Architecture

``` mermaid
graph TD
    subgraph Frontend
        A[Login Page /login] -->|POST /api/auth/login| B[Auth Service]
        B --> C[AuthContext]
        C -->|Authenticated| D[Protected Routes]
        E[Topbar Profile] -->|Logout| C
        F[API Client] -->|Bearer Token| G[FastAPI]
    end

    subgraph Backend
        G --> H[POST /api/auth/login]
        G --> I[GET /api/auth/me]
        G --> J[POST /api/auth/logout]
        H --> K[bcrypt Verification]
        K --> L[(MySQL users)]
        H --> M[JWT HS256]
        I --> M
        I --> L
    end
```

------------------------------------------------------------------------

# Authentication Model

Use:

``` text
JWT Bearer Token
        +
MySQL users table
        +
bcrypt password hashing
```

Token configuration must come from environment/configuration rather than
source code.

Required configuration:

``` env
JWT_SECRET=<strong-secret>
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440
```

Do not commit real secrets to Git.

For the frontend, the API base URL remains environment-driven:

``` env
VITE_API_BASE_URL=http://localhost:8000
```

------------------------------------------------------------------------

# STEP 1 --- Database & User Model

Add the `users` table to:

``` text
data/mysql_ddl.sql
```

Create:

``` text
backend/workflows/user_service.py
```

The table must contain:

``` text
user_id
username
email
password_hash
role
team
access_level
full_name
is_active
last_login_at
created_at
updated_at
```

Recommended constraints:

-   `user_id` is the primary key.
-   `username` is unique.
-   `email` is unique.
-   `is_active` defaults to `TRUE`.
-   timestamps use the existing Vigil MySQL conventions.
-   `password_hash` stores only the bcrypt hash.

Implement user-service functions for:

``` text
initialize_users_table()
ensure_demo_admin()
get_user_by_username_or_email()
get_user_by_id()
verify_password()
update_last_login()
```

The demo admin should be inserted only when it does not already exist.

Do not overwrite an existing user's password, role, email, or profile on
every application startup.

------------------------------------------------------------------------

# STEP 2 --- Password Hashing

Use bcrypt through the project's existing Python dependency conventions.

Password requirements:

-   Hash passwords before storage.
-   Verify passwords using bcrypt verification.
-   Never compare plaintext passwords directly against database values.
-   Never return `password_hash` from an API response.
-   Never log passwords.
-   Never include passwords in JWT claims.

If the project already has a password/security utility, reuse it instead
of creating a duplicate implementation.

------------------------------------------------------------------------

# STEP 3 --- JWT Authentication

Implement JWT creation and decoding in the authentication service.

JWT claims should contain only the minimum required identity
information, such as:

``` json
{
  "sub": "<user_id>",
  "username": "admin",
  "exp": "<expiration>"
}
```

Do not place:

``` text
password
password_hash
```

or other unnecessary sensitive information into the token.

JWT validation must check:

-   Signature.
-   Expiration.
-   Required subject/user identity.
-   User existence.
-   `is_active = TRUE`.

A valid JWT for a deleted/deactivated user must not grant application
access.

------------------------------------------------------------------------

# STEP 4 --- Authentication API

Create:

``` text
backend/api/routes/auth.py
```

Routes:

  Method   Path                 Purpose
  -------- -------------------- ----------------------------------------
  POST     `/api/auth/login`    Authenticate username/email + password
  GET      `/api/auth/me`       Return authenticated user
  POST     `/api/auth/logout`   Logout acknowledgement
  GET      `/api/auth/users`    Read-only user listing

### POST `/api/auth/login`

Request:

``` json
{
  "username": "admin",
  "password": "admin12345"
}
```

The `username` field may accept either username or email.

Successful response should contain:

``` json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "user": {
    "user_id": "...",
    "username": "admin",
    "email": "audit.officer@vigil.com",
    "full_name": "...",
    "role": "Audit Officer",
    "team": "Compliance",
    "access_level": "All"
  }
}
```

Do not return:

``` text
password_hash
```

Update `last_login_at` after successful authentication.

Invalid credentials must return:

``` text
401 Unauthorized
```

Use a generic authentication error rather than revealing whether the
username or password was incorrect.

------------------------------------------------------------------------

# STEP 5 --- Authenticated Dependency

Create a reusable FastAPI authentication dependency, for example:

``` text
get_current_user()
```

It must:

1.  Read the `Authorization: Bearer <token>` header.
2.  Decode and validate the JWT.
3.  Load the user from MySQL.
4.  Verify the user is active.
5.  Return the authenticated user.

Use this dependency for protected API routes.

Do not duplicate JWT parsing logic inside individual endpoints.

------------------------------------------------------------------------

# STEP 6 --- Protect Existing Backend APIs

Authentication should apply to the existing Vigil application APIs.

Protect the Phase 8/9 application routes, including:

``` text
/api/dashboard/*
/api/calls/*
/api/cases/*
/api/rm/*
/api/documents
/api/settings
/api/chat
```

The login endpoints themselves must remain publicly accessible:

``` text
/api/auth/login
/api/auth/me
```

`/api/auth/logout` requires an authenticated user.

The read-only `/api/auth/users` endpoint should also require
authentication.

Do not modify the underlying Phase 5--9 business logic just to add
authentication. Add authentication at the API boundary.

------------------------------------------------------------------------

# STEP 7 --- Logout Semantics

The architecture uses bearer JWTs.

`POST /api/auth/logout` should:

-   Require a valid authenticated user.
-   Return a successful acknowledgement.
-   Allow the frontend to clear the local token immediately.

Because this build uses stateless JWT authentication, logout does not
need to implement a token blacklist unless an existing project security
requirement specifically requires server-side revocation.

The frontend is responsible for removing the active token on logout.

------------------------------------------------------------------------

# STEP 8 --- Frontend API Client

Modify:

``` text
frontend/src/services/api.ts
```

The API client must:

-   Read the current access token from the chosen browser storage
    mechanism.
-   Add:

``` http
Authorization: Bearer <token>
```

to authenticated requests. - Not attach an invalid/empty token. - Handle
`401 Unauthorized` consistently. - Clear authentication state when a
session becomes invalid. - Dispatch/use a centralized unauthenticated
event rather than creating page-specific logout logic.

Do not hardcode:

``` text
http://localhost:8000
```

inside individual services.

Use:

``` env
VITE_API_BASE_URL
```

as the single frontend API base URL.

------------------------------------------------------------------------

# STEP 9 --- Auth Service

Create:

``` text
frontend/src/services/authService.ts
```

Types:

``` text
User
LoginCredentials
AuthResponse
```

Methods:

``` text
login(credentials)
getMe()
logout()
```

The service should remain a thin API layer.

Do not place React state or routing logic inside `authService.ts`.

------------------------------------------------------------------------

# STEP 10 --- Auth Context

Create:

``` text
frontend/src/context/AuthContext.tsx
```

State:

``` text
user: User | null
token: string | null
isAuthenticated: boolean
isLoading: boolean
```

Actions:

``` text
login(username, password)
logout()
```

Startup behavior:

``` text
Application starts
        ↓
Read stored token
        ↓
No token?
        ↓
Unauthenticated

Token exists
        ↓
GET /api/auth/me
        ↓
Valid → authenticated
Invalid/expired → clear token → unauthenticated
```

Do not assume that the existence of a token means the session is valid.

------------------------------------------------------------------------

# STEP 11 --- Storage

Persist the JWT so browser refresh does not immediately log the user
out.

For this demo build, use the existing frontend storage convention
consistently.

If `localStorage` is used:

``` text
vigil_access_token
vigil_user
```

Store only the minimum information needed for client state.

Never store:

``` text
password
password_hash
```

The `/api/auth/me` response remains the source of truth for validating
the stored session.

------------------------------------------------------------------------

# STEP 12 --- Login Page

Create:

``` text
frontend/src/pages/Login/index.tsx
```

The Login page should visually match Vigil's existing design language
rather than introducing an unrelated application style.

Required elements:

### Branding

-   Vigil shield/logo treatment.
-   Vigil name.
-   Short surveillance/compliance-oriented tagline.
-   Subtle animated pulse/accent.

### Login card

-   High-end dark/light compatible design.
-   Glassmorphic treatment where consistent with the existing UI.
-   Username / Email field.
-   Password field.
-   Show/hide password control.
-   Login button.
-   Loading state.
-   Clear authentication error.

### Demo credentials

Provide:

``` text
Fill Demo Credentials
```

This should populate:

``` text
Username: admin
Password: admin12345
```

Optionally show the demo user's metadata:

``` text
Audit Officer
Compliance
audit.officer@vigil.com
All
```

The button must still require the user to press Login.

### Security indicators

Show concise badges such as:

``` text
SEBI / AMFI Surveillance AI
Audit Trail Enforced
```

Do not make claims about security controls that are not actually
implemented.

------------------------------------------------------------------------

# STEP 13 --- Protected Routes

Create:

``` text
frontend/src/components/auth/ProtectedRoute.tsx
```

Behavior:

``` text
Not authenticated
        ↓
/login
        ↓
preserve intended destination

Authenticated
        ↓
render requested page
```

While `AuthContext` is checking a stored token:

``` text
isLoading = true
```

show a consistent loading state instead of briefly rendering the
protected application.

If a user visits:

``` text
/login
```

while already authenticated:

``` text
→ /
```

or the application's default Dashboard route.

------------------------------------------------------------------------

# STEP 14 --- Router Integration

Modify:

``` text
frontend/src/router.tsx
```

Add:

``` text
/login
```

Wrap all application routes in:

``` text
<ProtectedRoute>
```

Protected pages include the existing:

``` text
/
/calls
/cases
/rm/*
/documents
/settings
/chat
```

Do not alter existing page layouts.

When redirecting unauthenticated users to `/login`, preserve the
original path/query where practical so successful login can return the
user to the intended page.

------------------------------------------------------------------------

# STEP 15 --- App Provider Integration

Modify:

``` text
frontend/src/App.tsx
```

Wrap the application with:

``` text
<AuthProvider>
```

Ensure the provider is mounted above the router/components that call
`useAuth()`.

Do not create multiple independent AuthProviders.

------------------------------------------------------------------------

# STEP 16 --- Topbar Profile

Modify:

``` text
frontend/src/components/layout/Topbar.tsx
```

Use:

``` text
useAuth()
```

to display the actual authenticated user.

Display:

``` text
Full Name
Role
Team
Initials
```

The profile dropdown should contain:

``` text
Email
Role
Team
Access Level
Sign Out
```

The Sign Out action must:

1.  Call the auth logout flow.
2.  Clear stored authentication state.
3.  Redirect to `/login`.

If a confirmation dialog already exists in the design system, reuse it.

------------------------------------------------------------------------

# STEP 17 --- Sidebar

Modify:

``` text
frontend/src/components/layout/Sidebar.tsx
```

Show a compact authenticated-user indicator or sign-out action at the
bottom.

Do not duplicate complex profile logic already implemented in Topbar.

Reuse `useAuth()`.

------------------------------------------------------------------------

# STEP 18 --- 401 Handling

All protected API requests must handle:

``` text
401 Unauthorized
```

consistently.

Expected behavior:

``` text
API request
    ↓
401
    ↓
clear token/auth state
    ↓
redirect to /login
```

Do not leave the application in a state where the UI appears
authenticated while every backend request is returning 401.

Avoid redirect loops for:

``` text
/api/auth/login
/api/auth/me
```

------------------------------------------------------------------------

# STEP 19 --- CORS

Configure backend CORS for the frontend development origin.

The expected development setup is approximately:

``` text
Frontend: http://localhost:5173
Backend:  http://localhost:8000
```

Use the configured frontend origin rather than enabling unrestricted
production CORS.

Do not use:

``` text
allow_origins=["*"]
```

for authenticated browser requests in the final implementation.

------------------------------------------------------------------------

# STEP 20 --- Error Handling

Authentication endpoints must return structured JSON errors.

Examples:

### Invalid credentials

``` json
{
  "detail": "Invalid username or password"
}
```

### Missing token

``` json
{
  "detail": "Authentication required"
}
```

### Expired/invalid token

``` json
{
  "detail": "Authentication session is invalid or expired"
}
```

Frontend should convert these into user-friendly messages.

Never display backend stack traces to the user.

Never expose:

``` text
database errors
JWT secrets
password hashes
```

------------------------------------------------------------------------

# STEP 21 --- Do Not Break Existing APIs

After authentication is introduced:

-   Phase 8 case workflow must still work.
-   Phase 9 AI Chat must still work.
-   Existing frontend services must continue using the same response
    contracts.
-   Authentication should be an API boundary concern.
-   Do not duplicate case/call/finding retrieval logic inside
    authentication code.

The only intended behavioral change is that protected endpoints now
require a valid authenticated user.

------------------------------------------------------------------------

# STEP 22 --- Verification

## Backend verification

Run a real verification script and confirm:

### 1. Database

``` text
users table exists
```

### 2. Seed

``` text
admin exists
password_hash is bcrypt
plaintext password is not stored
```

### 3. Login

``` text
POST /api/auth/login
admin / admin12345
```

Confirm:

``` text
200
access_token exists
token_type = bearer
user profile exists
password_hash absent
```

### 4. Wrong password

Confirm:

``` text
POST /api/auth/login
wrong password
→ 401
```

### 5. Unknown user

Confirm:

``` text
POST /api/auth/login
unknown user
→ 401
```

### 6. Me

Use the returned token:

``` text
GET /api/auth/me
Authorization: Bearer <token>
```

Confirm the authenticated user is returned.

### 7. Protected endpoint without token

Example:

``` text
GET /api/dashboard/summary
```

without Authorization.

Confirm:

``` text
401
```

### 8. Protected endpoint with token

Repeat with:

``` text
Authorization: Bearer <token>
```

Confirm the real Dashboard response is returned.

### 9. Invalid token

Send an invalid/expired JWT.

Confirm:

``` text
401
```

------------------------------------------------------------------------

# STEP 23 --- Frontend Verification

Run:

``` bash
npm run build
```

Confirm there are no TypeScript/build errors.

Then verify through the browser:

### Test 1 --- Route protection

Navigate directly to:

``` text
http://localhost:5173/
```

without authentication.

Expected:

``` text
→ /login
```

### Test 2 --- Login

Click:

``` text
Fill Demo Credentials
```

Then click Login.

Expected:

``` text
POST /api/auth/login
→ Dashboard
```

### Test 3 --- Refresh persistence

After login:

``` text
Refresh browser
```

Expected:

``` text
session remains authenticated
```

and `/api/auth/me` validates the token.

### Test 4 --- Topbar

Confirm:

``` text
Audit Officer
Compliance
```

appear from the authenticated user data.

Open the profile dropdown and verify:

``` text
Email
Role
Team
Access = All
Sign Out
```

### Test 5 --- Protected API

Navigate through:

``` text
Dashboard
Calls
Cases
Case Detail
RM Analytics
Documents
Settings
AI Investigation
```

Confirm authenticated API requests contain the Bearer token and existing
functionality continues working.

### Test 6 --- Logout

Click:

``` text
Sign Out
```

Expected:

``` text
token cleared
auth state cleared
→ /login
```

Then attempt to open `/cases` directly.

Expected:

``` text
→ /login
```

### Test 7 --- Expired/invalid session

Replace the stored token with an invalid token or use an expired token.

Refresh.

Expected:

``` text
GET /api/auth/me
→ 401
→ token cleared
→ /login
```

------------------------------------------------------------------------

# STEP 24 --- Security Verification

Confirm all of the following:

-   Passwords are bcrypt-hashed.
-   Plaintext passwords are never stored.
-   Passwords are never logged.
-   Password hashes are never returned by APIs.
-   JWT secret comes from environment/configuration.
-   JWT expiration is enforced.
-   Inactive users cannot authenticate.
-   Protected APIs reject missing/invalid tokens.
-   Frontend does not hardcode backend URLs.
-   CORS is restricted to configured frontend origins.
-   No generic SQL execution tool exists.
-   Logout clears the browser-side authentication state.
-   Authentication does not bypass Phase 8 case workflow permissions or
    audit logging.

------------------------------------------------------------------------

# Required Report Back

Report the **actual implementation and verification results**, not
hypothetical output.

Include:

1.  Files created/modified.
2.  Database migration/DDL result.
3.  Confirmation that the demo admin exists with a bcrypt hash.
4.  Actual login HTTP status and response shape.
5.  Actual `/api/auth/me` result.
6.  Actual invalid-login result.
7.  Actual protected-endpoint result without a token.
8.  Actual protected-endpoint result with a valid token.
9.  `npm run build` result.
10. Browser verification results for:

-   `/login`
-   route protection
-   login
-   refresh persistence
-   Topbar profile
-   logout
-   invalid/expired session

11. Any implementation limitations or deviations from this prompt.

Do not report "PASS" for a test that was not actually executed.

------------------------------------------------------------------------

# What Good Looks Like

A successful Phase 14 implementation should result in:

``` text
Unauthenticated
      ↓
     /login
      ↓
admin + password
      ↓
POST /api/auth/login
      ↓
JWT + user
      ↓
AuthContext
      ↓
Protected Vigil Application
      ↓
Bearer token on API calls
```

and:

``` text
Browser refresh
      ↓
stored JWT
      ↓
GET /api/auth/me
      ↓
valid
      ↓
remain authenticated
```

while:

``` text
Invalid/expired JWT
      ↓
401
      ↓
clear session
      ↓
/login
```

The Login page should feel like a native part of Vigil, not a separate
template.

The authentication layer should protect the existing Phase 8/9 backend
without changing their business behavior.

Most importantly:

> **Authentication controls access to Vigil; it must never weaken the
> audit trail, case workflow, regulatory grounding, or evidence-chain
> integrity already implemented in Phases 3--10.**
