-- Run once per deployment, as a superuser. Replace the password with a generated secret.
CREATE ROLE wathiqa_app_ro LOGIN PASSWORD 'CHANGE_ME' IN ROLE wathiqa_ro;
ALTER ROLE wathiqa_app_ro SET statement_timeout = '3s';
ALTER ROLE wathiqa_app_ro SET default_transaction_read_only = on;
ALTER ROLE wathiqa_app_ro SET idle_in_transaction_session_timeout = '5s';
ALTER ROLE wathiqa_app_ro CONNECTION LIMIT 5;
