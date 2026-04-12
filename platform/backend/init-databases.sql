-- Cria databases adicionais no startup do Postgres.
-- O DB padrao (namastex) e criado pela env POSTGRES_DB.
-- Esse script cria DBs extras que outros servicos precisam.

SELECT 'CREATE DATABASE omni' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'omni')\gexec
SELECT 'CREATE DATABASE namastex_test' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'namastex_test')\gexec
