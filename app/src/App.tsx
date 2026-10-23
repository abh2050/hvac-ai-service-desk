import { Authenticator } from '@aws-amplify/ui-react';

// Sign-up is hidden: demo users are created by scripts/seed-users.sh with passwords in SSM.
export default function App() {
  return (
    <Authenticator hideSignUp>
      {({ signOut, user }) => (
        <main style={{ padding: 24 }}>
          <h1>Uptime Desk</h1>
          <p>Signed in as {user?.signInDetails?.loginId}. The console pages arrive with the next deploy.</p>
          <button onClick={signOut}>Sign out</button>
        </main>
      )}
    </Authenticator>
  );
}
