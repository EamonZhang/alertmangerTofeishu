curl -X POST http://127.0.0.1:9527/webhook \
  -H "Content-Type: application/json" \
  -d '{"alerts":[{"annotations":{"description":"desc","summary":"summary"},"endsAt":"2024-08-12T03:52:46.383Z","fingerprint":"b1abbf3f2a954d66","generatorURL":"http=1","labels":{"about":"io","alertname":"IO性能","instance":"bkb81","status":"严重告警"},"startsAt":"2024-08-12T03:52:01.383Z","status":"resolved"}]}'
