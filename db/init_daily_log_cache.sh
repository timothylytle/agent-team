#!/bin/bash
cd "$(dirname "$0")"
rm -f daily_log_cache.db
sqlite3 daily_log_cache.db < daily_log_cache_schema.sql
echo "Daily log cache initialized at $(pwd)/daily_log_cache.db"
