-- Interview question: "Do you also make static ads?"
-- YES: a creative can be a static or a carousel, and clients get a designer.
-- NO:  skip this file.

alter type public.creative_format add value if not exists 'Static';
alter type public.creative_format add value if not exists 'Carousel';

alter table public.creatives add column design_url text;
alter table public.clients   add column designer_id uuid references public.team(id) on delete set null;
