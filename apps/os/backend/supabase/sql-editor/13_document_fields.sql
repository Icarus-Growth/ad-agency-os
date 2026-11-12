-- SQL editor paste 13 of 18: 0014_document_fields.sql
-- Paste all of this into the Supabase SQL editor and press Run.
-- Wait for "Success" before you paste the next file.

-- =============================================================================
-- 0014  Ads: which fields are documents (see 0013)
--
-- The fields below open in the app's editor and in the AI connector's docs.*
-- actions. board = the card table; empty = the client page. The *_url column
-- stays: it is the "paste a link instead".
--
-- creatives.script_text is gone: its text is now the "script" document of each card.
-- Any text already in it is moved into a document first.
-- Safe to run twice.
-- =============================================================================

insert into public.document_fields (board, field_key, label, link_column) values
  ('creatives', 'script', 'Script', 'script_url')
on conflict on constraint document_fields_key do update
  set label = excluded.label, link_column = excluded.link_column;

do $move$
begin
  if exists (select 1 from information_schema.columns
             where table_schema = 'public' and table_name = 'creatives' and column_name = 'script_text') then
    insert into public.documents (client_id, board, card_id, field_key, body_md, word_count)
    select c.client_id, 'creatives', c.id, 'script', c.script_text,
           coalesce(array_length(regexp_split_to_array(btrim(c.script_text), '\s+'), 1), 0)
    from public.creatives c
    where btrim(coalesce(c.script_text, '')) <> ''
    on conflict on constraint documents_key do nothing;
    alter table public.creatives drop column script_text;
  end if;
end
$move$;
