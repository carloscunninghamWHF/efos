-- EFOS v0.4.31: permitir únicamente a miembros autorizados leer
-- archivos originales ya catalogados en el bucket PRIVADO efos-private.
-- No modifica ningún dato existente y no concede permisos de escritura.
-- Requiere las tablas efos_source_files y efos_organization_members
-- con RLS de membresía ya configurada, como en el proyecto Supabase activo.

DROP POLICY IF EXISTS "efos_private_member_cataloged_read" ON storage.objects;
CREATE POLICY "efos_private_member_cataloged_read"
ON storage.objects FOR SELECT TO authenticated
USING (
  bucket_id = 'efos-private'
  AND EXISTS (
    SELECT 1
    FROM public.efos_source_files f
    JOIN public.efos_organization_members m
      ON m.organization_id = f.organization_id
    WHERE f.bucket = storage.objects.bucket_id
      AND f.storage_path = storage.objects.name
      AND f.status = 'cataloged'
      AND m.user_id = (SELECT auth.uid())
  )
);
-- Verificar que efos-private sigue siendo un bucket PRIVADO:
-- SELECT id, public FROM storage.buckets WHERE id = 'efos-private';
-- SELECT policyname, cmd, roles FROM pg_policies
-- WHERE schemaname = 'storage' AND tablename = 'objects';
