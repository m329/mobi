drop table if exists users;
create table users (
usr text primary key,
pas text,
loc text,
lat real,
lon real,
geohash text
);

drop table if exists items;
create table items (
itm_id integer primary key,
itm_name text,
usr text,
prc real
);

drop table if exists wishlists;
create table wishlists (
usr text,
wishstr text
);
