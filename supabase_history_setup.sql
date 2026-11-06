-- Seam Carving Lab private image history.
-- Run in Supabase SQL Editor. Can be run again to replace the SAME project policies.
-- Create a PRIVATE storage bucket "seam-images" in Storage beforehand.
-- This uses the user's JWT via auth.uid(), never a service-role credential.
BEGIN;
CREATE TABLE IF NOT EXISTS public.image_history (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  operation text NOT NULL,
  source_name text NOT NULL DEFAULT '',
  input_path text NOT NULL,
  output_path text NOT NULL,
  input_width integer NOT NULL,
  input_height integer NOT NULL,
  output_width integer NOT NULL,
  output_height integer NOT NULL,
  details jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS image_history_owner_time
  ON public.image_history (user_id, created_at DESC);
ALTER TABLE public.image_history ENABLE ROW LEVEL SECURITY;
GRANT SELECT, INSERT, DELETE ON TABLE public.image_history TO authenticated;
REVOKE ALL ON TABLE public.image_history FROM anon;

DROP POLICY IF EXISTS history_select_own ON public.image_history;
DROP POLICY IF EXISTS history_insert_own ON public.image_history;
DROP POLICY IF EXISTS history_delete_own ON public.image_history;
CREATE POLICY history_select_own ON public.image_history
  FOR SELECT TO authenticated USING (user_id = (SELECT auth.uid()));
CREATE POLICY history_insert_own ON public.image_history
  FOR INSERT TO authenticated WITH CHECK (user_id = (SELECT auth.uid()));
CREATE POLICY history_delete_own ON public.image_history
  FOR DELETE TO authenticated USING (user_id = (SELECT auth.uid()));

-- Path pattern: <auth-user-uuid>/<random-run-id>_source.png and _output.png
DROP POLICY IF EXISTS image_files_select_own ON storage.objects;
DROP POLICY IF EXISTS image_files_insert_own ON storage.objects;
DROP POLICY IF EXISTS image_files_delete_own ON storage.objects;
CREATE POLICY image_files_select_own ON storage.objects
  FOR SELECT TO authenticated
  USING (bucket_id = 'seam-images' AND
    (storage.foldername(name))[1] = (SELECT auth.uid())::text);
CREATE POLICY image_files_insert_own ON storage.objects
  FOR INSERT TO authenticated
  WITH CHECK (bucket_id = 'seam-images' AND
    (storage.foldername(name))[1] = (SELECT auth.uid())::text);
CREATE POLICY image_files_delete_own ON storage.objects
  FOR DELETE TO authenticated
  USING (bucket_id = 'seam-images' AND
    (storage.foldername(name))[1] = (SELECT auth.uid())::text);
COMMIT;
