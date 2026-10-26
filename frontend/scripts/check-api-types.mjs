import { readFileSync } from 'node:fs'
import openapiTS, { astToString, COMMENT_HEADER } from 'openapi-typescript'

const ast = await openapiTS(new URL('../../docs/openapi.json', import.meta.url))
const generated = COMMENT_HEADER + astToString(ast)
if (generated !== readFileSync('src/generated/api-types.ts', 'utf8')) {
  throw new Error('API types are stale: run make api-generate')
}
