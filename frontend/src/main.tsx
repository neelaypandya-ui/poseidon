import { luma } from '@luma.gl/core'
import { webgl2Adapter } from '@luma.gl/webgl'

// Force WebGL2 — must happen before any Deck.gl import
luma.registerAdapters([webgl2Adapter])
luma.log.level = 1

import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>,
)
