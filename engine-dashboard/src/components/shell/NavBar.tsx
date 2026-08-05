import React from 'react';
import { Link, useLocation } from 'wouter';
import {
  LayoutDashboard,
  TerminalSquare,
  List,
  Layers,
  ShieldCheck,
  Activity,
  BarChart3,
  Terminal,
  Rocket,
} from 'lucide-react';

export function NavBar() {
  const [location] = useLocation();

  const navItems = [
    { href: '/', label: 'Overview', icon: LayoutDashboard, testid: 'nav-link-overview' },
    { href: '/workspace', label: 'Workspace', icon: TerminalSquare, testid: 'nav-link-workspace' },
    { href: '/sessions', label: 'Sessions', icon: List, testid: 'nav-link-sessions' },
    { href: '/retrieval', label: 'Retrieval Explorer', icon: Layers, testid: 'nav-link-retrieval' },
    { href: '/governance', label: 'Context Governance', icon: ShieldCheck, testid: 'nav-link-governance' },
    { href: '/runtime', label: 'Runtime', icon: Activity, testid: 'nav-link-runtime' },
    { href: '/benchmarks', label: 'Benchmarks', icon: BarChart3, testid: 'nav-link-benchmarks' },
    { href: '/developer', label: 'Developer', icon: Terminal, testid: 'nav-link-developer' },
    { href: '/release', label: 'Release', icon: Rocket, testid: 'nav-link-release' },
  ];

  return (
    <nav className="flex-none lg:w-[220px] border-r border-border-subtle bg-surface-1 flex flex-col pt-4">
      <div className="px-3 space-y-1">
        {navItems.map((item) => {
          const isActive = location === item.href;
          return (
            <Link key={item.href} href={item.href} data-testid={item.testid}>
              <div 
                className={`
                  flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors cursor-pointer
                  ${isActive 
                    ? 'bg-surface-2 text-accent' 
                    : 'text-text-secondary hover:bg-surface-2 hover:text-text-primary'
                  }
                `}
                aria-current={isActive ? 'page' : undefined}
              >
                <item.icon className={`w-4 h-4 ${isActive ? 'text-accent' : 'text-text-tertiary'}`} />
                <span className="hidden lg:inline">{item.label}</span>
              </div>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
