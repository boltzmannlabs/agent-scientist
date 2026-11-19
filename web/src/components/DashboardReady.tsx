import { useEffect } from 'react';

/** Dismiss the bundle-independent loading screen only after React commits. */
export function DashboardReady() {
  useEffect(() => { window.dispatchEvent(new Event('sci:dashboard-ready')); }, []);
  return null;
}
