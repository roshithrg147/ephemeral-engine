import React from 'react';
import { Route, Switch, Router as WouterRouter } from 'wouter';
import { AuthProvider } from './context/AuthContext';
import { ProtectedRoute } from './components/auth/ProtectedRoute';
import { RuntimeProvider } from './runtime/RuntimeContext';
import { AppShell } from './components/shell/AppShell';
import { Overview } from './pages/Overview';
import { Workspace } from './pages/Workspace';
import { Sessions } from './pages/Sessions';
import { RetrievalExplorer } from './pages/RetrievalExplorer';
import { ContextGovernance } from './pages/ContextGovernance';
import { RuntimeDashboard } from './pages/RuntimeDashboard';
import { BenchmarksPage } from './pages/BenchmarksPage';
import { DeveloperPage } from './pages/DeveloperPage';
import { ReleasePage } from './pages/ReleasePage';

function Router() {
  return (
    <Switch>
      <Route path="/" component={Overview} />
      <Route path="/workspace" component={Workspace} />
      <Route path="/sessions" component={Sessions} />
      <Route path="/retrieval" component={RetrievalExplorer} />
      <Route path="/governance" component={ContextGovernance} />
      <Route path="/runtime" component={RuntimeDashboard} />
      <Route path="/benchmarks" component={BenchmarksPage} />
      <Route path="/developer" component={DeveloperPage} />
      <Route path="/release" component={ReleasePage} />
      <Route>
        <div className="flex items-center justify-center h-full text-text-tertiary">
          404 - Not Found
        </div>
      </Route>
    </Switch>
  );
}

function App() {
  return (
    <AuthProvider>
      <ProtectedRoute>
        <RuntimeProvider>
          <WouterRouter base={import.meta.env.BASE_URL.replace(/\/$/, '')}>
            <AppShell>
              <Router />
            </AppShell>
          </WouterRouter>
        </RuntimeProvider>
      </ProtectedRoute>
    </AuthProvider>
  );
}

export default App;
