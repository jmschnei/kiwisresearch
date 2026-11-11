import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { DashboardLayout } from '@/components/DashboardLayout';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 5000, refetchInterval: 5000 },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <DashboardLayout />
    </QueryClientProvider>
  );
}

export default App;
