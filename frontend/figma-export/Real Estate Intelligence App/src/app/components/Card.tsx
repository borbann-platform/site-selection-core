import { HTMLAttributes, forwardRef } from 'react';
import { motion } from 'motion/react';

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  glass?: boolean;
  hover?: boolean;
}

export const Card = forwardRef<HTMLDivElement, CardProps>(
  ({ glass = true, hover = false, className = '', children, ...props }, ref) => {
    const baseStyles = 'rounded-xl p-6 transition-all duration-300';
    const glassStyles = glass ? 'glass' : 'bg-card border border-card-border shadow-md';
    const hoverStyles = hover ? 'hover:shadow-lg dark:hover:shadow-primary/10 light:hover:shadow-xl' : '';
    
    if (hover) {
      return (
        <motion.div
          ref={ref}
          whileHover={{ y: -4 }}
          className={`${baseStyles} ${glassStyles} ${hoverStyles} ${className}`}
          {...props}
        >
          {children}
        </motion.div>
      );
    }
    
    return (
      <div
        ref={ref}
        className={`${baseStyles} ${glassStyles} ${className}`}
        {...props}
      >
        {children}
      </div>
    );
  }
);

Card.displayName = 'Card';