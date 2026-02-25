import { motion } from 'motion/react';

interface ScoreGaugeProps {
  score: number;
  maxScore?: number;
  label?: string;
  size?: 'sm' | 'md' | 'lg';
}

export function ScoreGauge({ score, maxScore = 100, label, size = 'md' }: ScoreGaugeProps) {
  const percentage = (score / maxScore) * 100;
  const circumference = 2 * Math.PI * 45;
  const strokeDashoffset = circumference - (percentage / 100) * circumference;
  
  const sizes = {
    sm: { width: 80, fontSize: 'text-lg', strokeWidth: 6 },
    md: { width: 120, fontSize: 'text-2xl', strokeWidth: 8 },
    lg: { width: 160, fontSize: 'text-4xl', strokeWidth: 10 },
  };
  
  const config = sizes[size];
  
  const getColor = () => {
    if (percentage >= 80) return '#10B981'; // success
    if (percentage >= 60) return '#0EA5E9'; // primary
    if (percentage >= 40) return '#F59E0B'; // warning
    return '#EF4444'; // destructive
  };
  
  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative" style={{ width: config.width, height: config.width }}>
        <svg className="transform -rotate-90" width={config.width} height={config.width}>
          <circle
            cx={config.width / 2}
            cy={config.width / 2}
            r="45"
            stroke="rgba(148, 163, 184, 0.2)"
            strokeWidth={config.strokeWidth}
            fill="none"
          />
          <motion.circle
            cx={config.width / 2}
            cy={config.width / 2}
            r="45"
            stroke={getColor()}
            strokeWidth={config.strokeWidth}
            fill="none"
            strokeLinecap="round"
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset }}
            transition={{ duration: 1, ease: 'easeOut' }}
            style={{
              strokeDasharray: circumference,
            }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className={`${config.fontSize} font-bold`} style={{ color: getColor() }}>
            {Math.round(score)}
          </span>
          {maxScore !== 100 && (
            <span className="text-xs text-muted-foreground">/ {maxScore}</span>
          )}
        </div>
      </div>
      {label && (
        <span className="text-sm font-medium text-muted-foreground text-center">{label}</span>
      )}
    </div>
  );
}
