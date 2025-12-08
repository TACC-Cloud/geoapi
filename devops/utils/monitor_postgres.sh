#!/bin/bash
while true; do
  clear
  echo "=== PostgreSQL Status at $(date) ==="
  echo ""
  echo "--- All Database Connections ---"
  docker exec geoapi_postgres psql -U geoapi -d postgres -c "
    SELECT
      datname as database,
      COALESCE(application_name, '<unnamed>') as app,
      count(*) as connections,
      state
    FROM pg_stat_activity
    WHERE datname IS NOT NULL
    GROUP BY datname, application_name, state
    ORDER BY datname, connections DESC;
  "

  echo ""
  echo "--- Total Connections by Database ---"
  docker exec geoapi_postgres psql -U geoapi -d postgres -c "
    SELECT
      datname as database,
      count(*) as total_connections
    FROM pg_stat_activity
    WHERE datname IS NOT NULL
    GROUP BY datname
    ORDER BY total_connections DESC;
  "

  echo ""
  TOTAL=$(docker exec geoapi_postgres psql -U geoapi -d postgres -t -c "SELECT count(*) FROM pg_stat_activity WHERE datname IS NOT NULL;" | tr -d '[:space:]')
  echo "Total: $TOTAL connections across all databases"
  echo ""
  echo "Press Ctrl+C to stop | Refreshing every 2 seconds"
  sleep 2
done

