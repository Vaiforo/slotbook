import { QueryClient, QueryCache, MutationCache } from '@tanstack/react-query'
import { clearOwnerSession } from '@/lib/owner-session'
import { ApiError } from '@/lib/api'

export const queryClient = new QueryClient({
  queryCache: new QueryCache({
    onError: (error, query) => {
      if (query.queryKey[0] === 'owner' && error instanceof ApiError && error.status === 401)
        clearOwnerSession(queryClient)
    },
  }),
  mutationCache: new MutationCache({
    onError: (error, _variables, _context, mutation) => {
      if (
        mutation.options.mutationKey?.[0] === 'owner' &&
        error instanceof ApiError &&
        error.status === 401
      )
        clearOwnerSession(queryClient)
    },
  }),
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      retry: (count, error) =>
        count < 1 && !(error instanceof ApiError && error.status >= 400 && error.status < 500),
      retryDelay: 500,
    },
    mutations: { retry: false },
  },
})
