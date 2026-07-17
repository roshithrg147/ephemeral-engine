import React from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, MessageSquare } from 'lucide-react';

export default function Navigation() {
  return (
    <nav className="w-64 bg-gray-900 border-r border-gray-800 flex flex-col h-screen shrink-0">
      <div className="p-6 border-b border-gray-800">
        <h1 className="text-xl font-bold text-emerald-400 tracking-wider">SC-EVM</h1>
        <p className="text-xs text-gray-500 mt-1">Control Plane</p>
      </div>
      
      <div className="flex-1 py-4 flex flex-col gap-2 px-3">
        <NavLink 
          to="/"
          className={({ isActive }) => 
            `flex items-center gap-3 px-4 py-3 rounded-md transition-colors ${
              isActive 
                ? 'bg-emerald-900/20 text-emerald-400 border border-emerald-800/50' 
                : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800'
            }`
          }
        >
          <LayoutDashboard size={18} />
          <span className="font-medium text-sm">Analytics</span>
        </NavLink>
        
        <NavLink 
          to="/chat"
          className={({ isActive }) => 
            `flex items-center gap-3 px-4 py-3 rounded-md transition-colors ${
              isActive 
                ? 'bg-emerald-900/20 text-emerald-400 border border-emerald-800/50' 
                : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800'
            }`
          }
        >
          <MessageSquare size={18} />
          <span className="font-medium text-sm">Interactive Terminal</span>
        </NavLink>
      </div>

      <div className="p-4 border-t border-gray-800 text-xs text-gray-600 text-center">
        v2.1.4 (Ephemeral Build)
      </div>
    </nav>
  );
}
