import { initializeApp } from 'firebase/app';
import { getAuth } from 'firebase/auth';

const apiKey = import.meta.env.VITE_FIREBASE_API_KEY;
const projectId = import.meta.env.VITE_FIREBASE_PROJECT_ID;
// Firebase web config is public identification, never the Gemini secret.
export let auth = apiKey && projectId ? getAuth(initializeApp({apiKey, projectId,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN})) : null;
export function configureAuth(config?:{apiKey:string;projectId:string;authDomain:string;appId?:string}) {
  if(!auth&&config?.apiKey&&config.projectId)auth=getAuth(initializeApp(config));
  return auth;
}
