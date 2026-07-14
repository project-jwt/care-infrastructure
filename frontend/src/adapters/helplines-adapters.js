// Adapters for spec §Helplines. Requires a valid JWT (handleFetch attaches
// it automatically); both roles may call — helplines sit behind login only.

import { handleFetch } from './fetch-helpers';

// The pre-loaded helplines, in seed order:
// [{ id, name, phone, hours, description }]
export const listHelplines = () => handleFetch('/api/helplines');
