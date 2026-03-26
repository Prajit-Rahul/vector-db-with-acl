-- vecgate/sql/003_rls.sql
-- Optional defense-in-depth RLS on chunks.
-- Enable with: vecgate init --enable-rls
-- Runtime queries must call: SELECT set_config('app.current_user_facets', '1,2,3', true)
ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE chunks FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS chunks_acl ON chunks;
CREATE POLICY chunks_acl ON chunks FOR ALL
    USING (
        facet_id = ANY(
            string_to_array(
                current_setting('app.current_user_facets', true), ','
            )::int[]
        )
    );
