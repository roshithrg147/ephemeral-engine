import React from 'react';
import { Link, useLocation } from 'wouter';
import { LayoutDashboard, TerminalSquare, List } from 'lucide-react';

export function NavBar() {
  const [location] = useLocation();

  const navItems = [
    { href: '/', label: 'Overview', icon: LayoutDashboard, testid: 'nav-link-overview' },
    { href: '/workspace', label: 'Workspace', icon: TerminalSquare, testid: 'nav-link-workspace' },
    { href: '/sessions', label: 'Sessions', icon: List, testid: 'nav-link-sessions' },
  ];

  return (
    <nav className="flex-none lg:w-[200px] border-r border-border-subtle bg-surface-1 flex flex-col pt-4">
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
