# Goose OKF round-trip validation

- OKF entries loaded: 5
- Memanto rows mapped: 5
- Passed: True

## Type counts

- decision: 1
- event: 1
- fact: 2
- preference: 1

## Recall parity checks

- PASS: Which agent generated the migrated sessions? — expected `goose`
- PASS: What deployment preference was preserved? — expected `npm test, deploying`
- PASS: Which locking decision should survive the migration? — expected `postgres, redis`
