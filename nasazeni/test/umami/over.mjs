// Přihlášení i odeslání události procházejí běžným HTTP API místního Umami.
import { readFileSync } from 'node:fs';
import { setTimeout as wait } from 'node:timers/promises';

const importing = process.argv[2] === '--import';
const input = readFileSync(0, 'utf8');
const days = importing ? JSON.parse(input) : null;
const password = importing ? days.password : input.trimEnd();
const base = 'http://127.0.0.1:3000/api';
const initialUser = '41e2b680-648e-4b09-bcd7-3e2b10c06264';
const website = 'bd6c414c-cb6d-43e1-a9b7-6487272a450d';
const domain = 'polarita.test';
const event = 'zkouska-predani-svj';
if (password.length < 8) throw new Error('Chybí testovací přístup ředitelství.');

let token;
async function api(path, body, accept = []) {
  const headers = { 'user-agent': 'Polarita-TEST/1.0 (interni prijem konverzi)' };
  if (body) headers['content-type'] = 'application/json';
  if (token && path !== '/send') headers.authorization = 'Bearer ' + token;
  const response = await fetch(base + path, {
    method: body ? 'POST' : 'GET', headers, body: body ? JSON.stringify(body) : undefined,
    redirect: 'error', signal: AbortSignal.timeout(180000),
  });
  if (accept.includes(response.status)) return null;
  if (!response.ok) throw new Error('Umami vrátilo ' + response.status + ' pro ' + path.split('?')[0]);
  if (path === '/send' && response.headers.has('set-cookie')) throw new Error('Sběr události nastavil cookie.');
  return response.json();
}

const login = (username, pass) => api('/auth/login', { username, password: pass }, [401]);
let account = await login('spravce', password);
if (!account && !importing) {
  account = await login('admin', password) ?? await login('admin', 'umami');
  if (!account || account.user.id !== initialUser || !account.user.isAdmin) throw new Error('Nesouhlasí výchozí účet TEST.');
  token = account.token;
  if (account.user.passwordChangeRequired) {
    token = (await api('/me/password', { currentPassword: 'umami', newPassword: password })).token;
  }
  await api('/users/' + initialUser, { username: 'spravce' });
  token = undefined;
  account = await login('spravce', password);
}
if (!account?.user?.isAdmin || account.user.id !== initialUser || account.user.passwordChangeRequired) throw new Error('Umami nepotvrdilo správce.');
token = account.token;
const page = '/websites/' + website;
const site = await api(page, undefined, [404,403,401]) ??
  await api('/websites', { id: website, name: 'Ředitelství Polarity TEST', domain });
if (site.id !== website || site.domain !== domain) throw new Error('Umami nepotvrdilo měřený web.');
async function count(name, start, end) {
  const metrics = await api(page + '/metrics?type=event&startAt=' + start + '&endAt=' + end);
  const row = metrics.find(item => item.x === name);
  const value = row ? Number(row.y) : 0;
  if (!Number.isSafeInteger(value) || value < 0) throw new Error('Umami nevrátilo počet událostí.');
  return value;
}
if (importing) {
  const eventName = 'prevzeti-sanonu';
  const report = [];
  for (const { day, received } of days.rows) {
    const start = Date.parse(day + 'T00:00:00Z');
    const end = start + 86400000 - 1;
    if (!Number.isFinite(start) || !Number.isSafeInteger(received) || received < 0) throw new Error('Neplatný denní součet.');
    const before = await count(eventName, start, end);
    if (before > received) throw new Error('Umami má více převzetí než zdrojový registr.');
    for (let i = before; i < received; i++) {
      await api('/send', { type: 'event', payload: { website, hostname: domain, url: '/prevzeti-sanonu/',
        name: eventName, timestamp: start / 1000, language: 'cs' } });
    }
    if (await count(eventName, start, end) !== received) throw new Error('Nesouhlasí kontrolní čtení denního součtu.');
    report.push({ day, received });
  }
  console.log(JSON.stringify({ available: true, website, event: eventName, days: report, checked_at: new Date().toISOString() }));
  process.exit(0);
}
let total = await count(event, 0, Date.now());
if (total === 0) {
  await api('/send', { type: 'event', payload: { website, hostname: domain, url: '/kalkulacka-svj/', name: event, language: 'cs' } });
  for (let retry = 0; retry < 12 && !total; retry++) { await wait(1000); total = await count(event, 0, Date.now()); }
}
if (!Number.isSafeInteger(total) || total < 1) throw new Error('Analytika nevrátila zapsanou zkušební událost.');
console.log('Umami potvrdilo správce ředitelství a přes vlastní API načetlo testovací událost kalkulačky.');
console.log('Počet zaznamenaných testovacích událostí: ' + total);
