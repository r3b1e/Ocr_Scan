/**
 * RemindRx theme. Exposes the same `useTheme().theme.colors` keys as
 * HealthApp's ThemeContext, so components ported from it work unchanged.
 */
export const colors = {
    primary: '#0EA5E9',
    primaryDark: '#0284C7',
    primaryTint: '#E0F2FE',
    accent: '#FB7185',
    accentOrange: '#F97316',
    accentTint: '#FFE4E6',
    success: '#10B981',
    successTint: '#D1FAE5',
    background: '#F8FAFC',
    surface: '#FFFFFF',
    secondary: '#F1F5F9',
    border: '#E2E8F0',
    text: '#0F172A',
    textSecondary: '#64748B',
    error: '#E11D48',
    warning: '#F97316',
};

export const theme = { colors };

export const useTheme = () => ({ theme, isDark: false });

export const shadow = {
    shadowColor: '#0F172A',
    shadowOpacity: 0.06,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 4 },
    elevation: 2,
};
