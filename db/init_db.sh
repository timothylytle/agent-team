#!/bin/bash
cd "$(dirname "$0")"
rm -f crm.db
sqlite3 crm.db < schema.sql
echo "Database initialized at $(pwd)/crm.db"
