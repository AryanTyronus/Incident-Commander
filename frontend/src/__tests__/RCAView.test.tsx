import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { RCAView } from '../components/RCAView';
import { rcaData } from '../test/fixtures';

describe('RCAView', () => {
  it('renders RCA header', () => {
    render(<RCAView rca={rcaData} />);
    expect(screen.getByText('Root Cause Analysis')).toBeInTheDocument();
  });

  it('displays confidence score as percentage', () => {
    render(<RCAView rca={rcaData} />);
    expect(screen.getByText('87%')).toBeInTheDocument();
  });

  it('displays confidence band', () => {
    render(<RCAView rca={rcaData} />);
    expect(screen.getByText('HIGH')).toBeInTheDocument();
  });

  it('displays primary hypothesis title', () => {
    render(<RCAView rca={rcaData} />);
    expect(screen.getByText(/Validation boundary condition changed/)).toBeInTheDocument();
  });

  it('displays primary hypothesis explanation', () => {
    render(<RCAView rca={rcaData} />);
    expect(screen.getByText(/The commit changed > to >=/)).toBeInTheDocument();
  });

  it('displays observed facts', () => {
    render(<RCAView rca={rcaData} />);
    expect(screen.getByText('Observed Facts')).toBeInTheDocument();
    expect(screen.getByText(/Validation errors started after deploy/)).toBeInTheDocument();
  });

  it('displays inferred facts', () => {
    render(<RCAView rca={rcaData} />);
    expect(screen.getByText('Inferred Facts')).toBeInTheDocument();
    expect(screen.getByText(/Zero-amount transactions are now passing/)).toBeInTheDocument();
  });

  it('displays uncertainties', () => {
    render(<RCAView rca={rcaData} />);
    expect(screen.getByText('Uncertainties')).toBeInTheDocument();
    expect(screen.getByText(/No direct test coverage/)).toBeInTheDocument();
  });
});
