import Link from 'next/link';

const navItems = [
  { href: '/', label: 'Dashboard' },
  { href: '/incidents', label: 'Incidents' },
  { href: '/agent/runs', label: 'Agent Runs' },
  { href: '/approvals', label: 'Approvals' },
  { href: '/knowledge', label: 'Knowledge' },
  { href: '/evals', label: 'Evals' },
];

export function Nav() {
  return (
    <nav className="global-nav" aria-label="Primary">
      <div className="global-nav-inner">
        <Link href="/" className="global-nav-brand">
          Ops Agent
        </Link>
        <ul className="global-nav-list">
          {navItems.map((item) => (
            <li key={item.href}>
              <Link href={item.href}>{item.label}</Link>
            </li>
          ))}
        </ul>
      </div>
    </nav>
  );
}
