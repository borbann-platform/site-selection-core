import { motion } from 'motion/react';

interface ProgressBarProps {
  value: number;
  max?: number;
  color?: 'primary' | 'success' | 'warning' | 'destructive';
  className?: string;
}

export function ProgressBar({ value, max = 100, color = 'primary', className = '' }: ProgressBarProps) {
  const percentage = Math.min((value / max) * 100, 100);
  
  const colors = {
    primary: 'bg-primary',
    success: 'bg-success',
    warning: 'bg-warning',
    destructive: 'bg-destructive',
  };
  
  return (
    <div className={`w-full h-2 bg-secondary rounded-full overflow-hidden ${className}`}>
      <motion.div
        className={`h-full rounded-full ${colors[color]}`}
        initial={{ width: 0 }}
        animate={{ width: `${percentage}%` }}
        transition={{ duration: 0.5, ease: 'easeOut' }}
      />
    </div>
  );
}
