import { useEffect, useState } from 'react';
import { Authenticator } from '@aws-amplify/ui-react';
import { BrowserRouter, NavLink, Navigate, Route, Routes } from 'react-router-dom';
import { api, type Me } from './api';
import Scenarios from './pages/Scenarios';
import Pipeline from './pages/Pipeline';
import AssetView from './pages/AssetView';
import Diagnosis from './pages/Diagnosis';
import WorkOrders from './pages/WorkOrders';
import Dispatch from './pages/Dispatch';
import Assistant from './pages/Assistant';
import Evidence from './pages/Evidence';

function Shell({ signOut }: { signOut?: () => void }) {
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    api<Me>('/me').then(setMe).catch((e) => setError(String(e.message)));
  }, []);
  const links: [string, string][] = [
    ['/scenarios', 'Scenario launcher'], ['/pipeline', 'Live pipeline'], ['/asset', 'Asset view'],
    ['/diagnosis', 'Diagnosis'], ['/work-orders', 'Work orders'], ['/dispatch', 'Dispatch board'],
    ['/assistant', 'Technician assistant'], ['/evidence', 'Evidence'],
  ];
  return (
    <div className="shell">
      <nav className="nav" aria-label="Main">
        <div className="brand">Uptime Desk</div>
        <div className="who">{me ? `${me.role}${me.technician_id ? ` ${me.technician_id}` : ''}` : error || 'loading'}</div>
        {links.map(([to, label]) => (
          <NavLink key={to} to={to}>{label}</NavLink>
        ))}
        <button className="secondary" style={{ marginTop: 'auto' }} onClick={signOut}>Sign out</button>
      </nav>
      <main className="content">
        <Routes>
          <Route path="/" element={<Navigate to={me?.role === 'technician' ? '/assistant' : '/scenarios'} replace />} />
          <Route path="/scenarios" element={<Scenarios me={me} />} />
          <Route path="/pipeline" element={<Pipeline />} />
          <Route path="/asset" element={<AssetView />} />
          <Route path="/diagnosis" element={<Diagnosis />} />
          <Route path="/work-orders" element={<WorkOrders me={me} />} />
          <Route path="/dispatch" element={<Dispatch />} />
          <Route path="/assistant" element={<Assistant />} />
          <Route path="/evidence" element={<Evidence />} />
        </Routes>
      </main>
    </div>
  );
}

// Sign-up is hidden: the demo users are created by scripts/seed-users.sh with passwords in SSM.
export default function App() {
  return (
    <Authenticator hideSignUp>
      {({ signOut }) => (
        <BrowserRouter>
          <Shell signOut={signOut} />
        </BrowserRouter>
      )}
    </Authenticator>
  );
}
