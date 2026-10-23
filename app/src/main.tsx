import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { Amplify } from 'aws-amplify';
import { STATIC } from './mode';
import '@aws-amplify/ui-react/styles.css';
import './index.css';
import App from './App';

// amplify_outputs.json exists only in Amplify builds; the static demo has no Cognito.
const outputs = Object.values(import.meta.glob('../amplify_outputs.json', { eager: true, import: 'default' }))[0];
if (!STATIC && outputs) Amplify.configure(outputs as Parameters<typeof Amplify.configure>[0]);

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
