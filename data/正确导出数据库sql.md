```
pg_dump -U postgres -h localhost -p 5432 -d fashion_ai --encoding=UTF8 --no-owner --no-privileges --clean --if-exists --inserts --format=plain --file=data/fashion_ai_export.sql
```
