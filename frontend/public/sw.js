// Minimal service worker — exists only so "Add to Home Screen" installs
// cleanly (architecture 5.4/§5). Not used for offline trading: every
// fetch just passes straight through to the network.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));
self.addEventListener("fetch", () => {});
