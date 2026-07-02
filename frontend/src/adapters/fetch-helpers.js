// TODO: shared handleFetch that:
//   - reads the JWT from localStorage (key: 'token') and attaches Authorization: Bearer <jwt>
//   - sets Content-Type: application/json when a body is provided
//   - returns { data, error } so callers never throw
