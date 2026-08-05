import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { Overview } from '../pages/Overview';
import { RetrievalExplorer } from '../pages/RetrievalExplorer';
import { ContextGovernance } from '../pages/ContextGovernance';
import { RuntimeDashboard } from '../pages/RuntimeDashboard';
import { BenchmarksPage } from '../pages/BenchmarksPage';
import { DeveloperPage } from '../pages/DeveloperPage';
import { ReleasePage } from '../pages/ReleasePage';
import { RuntimeProvider } from '../runtime/RuntimeContext';

describe('Dashboard Developer Preview MVP Pages', () => {
  it('renders Overview page 10-second health KPIs cleanly', () => {
    render(
      <RuntimeProvider>
        <Overview />
      </RuntimeProvider>
    );
    expect(screen.getByText(/System Operational Status/i)).toBeDefined();
    expect(screen.getByText(/Active Tenant Sessions/i)).toBeDefined();
    expect(screen.getByText(/Retrieval Latency \(P95\)/i)).toBeDefined();
  });

  it('renders Retrieval Explorer explainability panel', () => {
    render(<RetrievalExplorer />);
    expect(screen.getByText(/Retrieval Explorer/i)).toBeDefined();
    expect(screen.getByText(/Explainability Panel/i)).toBeDefined();
    expect(screen.getAllByText(/Semantic Vector/i).length).toBeGreaterThan(0);
  });

  it('renders Context Governance prompt budget & audit rationale', () => {
    render(<ContextGovernance />);
    expect(screen.getByText(/Context Governance/i)).toBeDefined();
    expect(screen.getByText(/Total Token Budget/i)).toBeDefined();
    expect(screen.getByText(/Admitted Context Blocks/i)).toBeDefined();
    expect(screen.getByText(/Evicted Context Blocks/i)).toBeDefined();
  });

  it('renders Runtime Dashboard provider health & circuit breakers', () => {
    render(<RuntimeDashboard />);
    expect(screen.getByText(/Runtime Dashboard/i)).toBeDefined();
    expect(screen.getByText(/OpenAI API/i)).toBeDefined();
    expect(screen.getByText(/Routing Distribution/i)).toBeDefined();
  });

  it('renders Benchmarks page trend charts & metrics', () => {
    render(<BenchmarksPage />);
    expect(screen.getByText(/Deterministic Benchmarks/i)).toBeDefined();
    expect(screen.getAllByText(/Precision@5/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Retrieval Quality Trend/i).length).toBeGreaterThan(0);
  });

  it('renders Developer page engineering capability matrix', () => {
    render(<DeveloperPage />);
    expect(screen.getByText(/Developer & Engineering Metadata/i)).toBeDefined();
    expect(screen.getByText(/Adaptive Outlier Thresholding/i)).toBeDefined();
    expect(screen.getByText(/3-Way Hybrid RRF Fusion/i)).toBeDefined();
  });

  it('renders Release page quality gates & approval status', () => {
    render(<ReleasePage />);
    expect(screen.getByText(/Release Governance & Approval Center/i)).toBeDefined();
    expect(screen.getByText(/Mandatory Release Quality Gates/i)).toBeDefined();
    expect(screen.getByText(/Benchmark Comparison/i)).toBeDefined();
  });
});
