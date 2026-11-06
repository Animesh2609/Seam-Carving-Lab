# Private image dashboard — Supabase setup

The dashboard is included in the project, but persistence requires a **private Storage bucket** and the provided SQL policies. Without these, the dashboard shows account information and the temporary image preview but cannot save permanent image history.

## Step 1 — Create private storage

In Supabase Dashboard → Storage → New bucket:
- Name: `seam-images` (exactly)
- Access: **Private** (not Public)
- Allowed MIME type: `image/png` if available
- Max per-file size: 8 MB or more, according to your plan

## Step 2 — Create the history table and policies

Open Supabase → SQL Editor → New query. Paste the entire `supabase_history_setup.sql` file and click Run. The SQL is repeatable for the named policies; it does not delete existing saved records. It creates metadata table `public.image_history` and Row Level Security policies for per-user records and Storage paths.

The SQL uses `auth.uid()` to tie records/files to the logged-in Supabase user. **No service-role key is required.**

## Step 3 — Test

1. Log in with email/password to your Streamlit app. Dashboard will open automatically.
2. Select Workbench, upload a photo and run seam carving.
3. Under output comparison, click **Save input & result to my dashboard**.
4. Open My dashboard. Confirm your original and output appear and that you can download/delete a saved entry.
5. Sign out, create/login with a different test account and confirm the other user's images do **not** appear.

## How long are images kept?

- Original/result image pairs are stored until deleted by the user (or project owner) and are not automatically removed when Streamlit restarts.
- An image currently open in the workbench appears in the dashboard as an in-memory *session preview only*; it is cleared on logout and not saved to Supabase unless requested.
- The dashboard lists the 50 most recent records. Pagination is not implemented.
- Account deletion cascades metadata, but Storage files may require a separate cleanup job. This is a course prototype, not a fully audited production gallery service.

## Troubleshooting

- `HTTP 404` from database: the SQL table has not been created or its name differs.
- `HTTP 403` from Storage: the bucket is not private, the RLS policies are missing, the JWT expired, or paths are misconfigured.
- Invalid token: sign out and log back in.
- A picture didn't appear: did you click Save? Simply uploading a photo does not permanently store it.
