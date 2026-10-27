/** @type {import('tailwindcss').Config} */
export default {
    content: ['./index.html', './src/**/*.{ts,tsx}'],
    theme: {
        extend: {
            colors: {
                primary: { DEFAULT: '#0EA5E9', dark: '#0284C7', tint: '#E0F2FE' },
                coral: { DEFAULT: '#FB7185', dark: '#E11D48', tint: '#FFE4E6' },
                orange: { DEFAULT: '#F97316', tint: '#FFEDD5' },
                ice: '#F8FAFC',
                ink: '#0F172A',
                muted: '#64748B',
                line: '#E2E8F0',
            },
            fontFamily: {
                sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
            },
            boxShadow: {
                card: '0 1px 2px rgba(15,23,42,0.04), 0 4px 16px rgba(15,23,42,0.05)',
                lift: '0 8px 24px rgba(14,165,233,0.25)',
            },
            keyframes: {
                'sheet-up': { from: { transform: 'translateY(100%)' }, to: { transform: 'translateY(0)' } },
                'fade-in': { from: { opacity: 0 }, to: { opacity: 1 } },
                'pop-in': { from: { opacity: 0, transform: 'scale(.92)' }, to: { opacity: 1, transform: 'scale(1)' } },
                ring: { '0%,100%': { transform: 'rotate(0)' }, '20%': { transform: 'rotate(-14deg)' }, '40%': { transform: 'rotate(12deg)' }, '60%': { transform: 'rotate(-8deg)' }, '80%': { transform: 'rotate(6deg)' } },
                pulse2: { '0%': { boxShadow: '0 0 0 0 rgba(251,113,133,.55)' }, '100%': { boxShadow: '0 0 0 28px rgba(251,113,133,0)' } },
            },
            animation: {
                'sheet-up': 'sheet-up .28s cubic-bezier(.2,.8,.2,1)',
                'fade-in': 'fade-in .2s ease-out',
                'pop-in': 'pop-in .25s cubic-bezier(.2,.8,.2,1)',
                ring: 'ring 1s ease-in-out infinite',
                pulse2: 'pulse2 1.4s ease-out infinite',
            },
        },
    },
    plugins: [],
};
