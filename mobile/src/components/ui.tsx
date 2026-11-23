import Ionicons from '@expo/vector-icons/Ionicons';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import {
  ActivityIndicator,
  Animated,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  View,
  type StyleProp,
  type ViewStyle,
} from 'react-native';
import { SafeAreaView, type Edge } from 'react-native-safe-area-context';
import Svg, { Defs, LinearGradient, Path, Stop } from 'react-native-svg';

import { useApp } from '../state/AppContext';
import { font, radius, space, touch, type IconName } from '../theme/theme';

export function Screen({ children, scroll = true, edges = ['top'] as Edge[], refreshControl }: {
  children: ReactNode;
  scroll?: boolean;
  edges?: Edge[];
  refreshControl?: React.ComponentProps<typeof ScrollView>['refreshControl'];
}) {
  const { c } = useApp();
  return (
    <SafeAreaView edges={edges} style={{ flex: 1, backgroundColor: c.bg }}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        {scroll ? (
          <ScrollView
            contentContainerStyle={{ padding: space.m, paddingBottom: space.xxl, gap: space.m }}
            keyboardShouldPersistTaps="handled"
            refreshControl={refreshControl}
          >
            {children}
          </ScrollView>
        ) : (
          <View style={{ flex: 1, padding: space.m, gap: space.m }}>{children}</View>
        )}
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

export function FadeIn({ children, delay = 0, style }: { children: ReactNode; delay?: number; style?: StyleProp<ViewStyle> }) {
  const v = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    Animated.timing(v, { toValue: 1, duration: 320, delay, useNativeDriver: true }).start();
  }, [v, delay]);
  return (
    <Animated.View style={[style, { opacity: v, transform: [{ translateY: v.interpolate({ inputRange: [0, 1], outputRange: [8, 0] }) }] }]}>
      {children}
    </Animated.View>
  );
}

export function Card({ children, style, accent }: { children: ReactNode; style?: StyleProp<ViewStyle>; accent?: string }) {
  const { c } = useApp();
  return (
    <View
      style={[
        { backgroundColor: c.card, borderRadius: radius.l, padding: space.m, borderWidth: 1, borderColor: accent ?? c.border, gap: space.s },
        style,
      ]}
    >
      {children}
    </View>
  );
}

export function T({ children, v = 'body', color, style, numberOfLines, selectable }: {
  children: ReactNode;
  v?: keyof typeof font;
  color?: string;
  style?: StyleProp<import('react-native').TextStyle>;
  numberOfLines?: number;
  selectable?: boolean;
}) {
  const { c } = useApp();
  return (
    <Text style={[font[v], { color: color ?? c.text }, style]} numberOfLines={numberOfLines} selectable={selectable} maxFontSizeMultiplier={1.8}>
      {children}
    </Text>
  );
}

export function Button({ title, onPress, icon, variant = 'primary', disabled, loading, style, accessibilityHint }: {
  title: string;
  onPress: () => void;
  icon?: IconName;
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  disabled?: boolean;
  loading?: boolean;
  style?: StyleProp<ViewStyle>;
  accessibilityHint?: string;
}) {
  const { c } = useApp();
  const bg = variant === 'primary' ? c.teal : variant === 'secondary' ? c.cardAlt : variant === 'danger' ? c.red : 'transparent';
  const fg = variant === 'primary' ? c.onAccent : variant === 'danger' ? '#fff' : variant === 'ghost' ? c.teal : c.text;
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled || loading}
      accessibilityRole="button"
      accessibilityState={{ disabled: !!(disabled || loading), busy: !!loading }}
      accessibilityLabel={title}
      accessibilityHint={accessibilityHint}
      style={({ pressed }) => [
        styles.button,
        { backgroundColor: bg, opacity: disabled ? 0.45 : pressed ? 0.85 : 1, borderColor: variant === 'secondary' ? c.border : 'transparent' },
        style,
      ]}
    >
      {loading ? <ActivityIndicator color={fg} /> : icon ? <Ionicons name={icon} size={20} color={fg} /> : null}
      <Text style={[font.h3, { color: fg, flexShrink: 1, textAlign: 'center' }]} maxFontSizeMultiplier={1.6}>
        {title}
      </Text>
    </Pressable>
  );
}

export function IconButton({ icon, label, onPress, color }: { icon: IconName; label: string; onPress: () => void; color?: string }) {
  const { c } = useApp();
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={label}
      hitSlop={8}
      style={({ pressed }) => ({ width: touch, height: touch, alignItems: 'center', justifyContent: 'center', borderRadius: radius.pill, opacity: pressed ? 0.6 : 1 })}
    >
      <Ionicons name={icon} size={22} color={color ?? c.textSecondary} />
    </Pressable>
  );
}

export function Chip({ label, selected, onPress, color }: { label: string; selected: boolean; onPress: () => void; color?: string }) {
  const { c } = useApp();
  const tint = color ?? c.teal;
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityState={{ selected }}
      style={{
        minHeight: 40,
        paddingHorizontal: space.m,
        borderRadius: radius.pill,
        justifyContent: 'center',
        borderWidth: 1,
        borderColor: selected ? tint : c.border,
        backgroundColor: selected ? tint + '22' : c.card,
      }}
    >
      <Text style={[font.label, { color: selected ? tint : c.textSecondary }]} maxFontSizeMultiplier={1.6}>
        {label}
      </Text>
    </Pressable>
  );
}

export function SectionTitle({ children, right }: { children: ReactNode; right?: ReactNode }) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: space.s }}>
      <T v="h3" style={{ flex: 1 }}>{children}</T>
      {right}
    </View>
  );
}

export function ToggleRow({ label, hint, value, onChange }: { label: string; hint?: string; value: boolean; onChange: (v: boolean) => void }) {
  const { c } = useApp();
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.m, minHeight: touch }}>
      <View style={{ flex: 1 }}>
        <T>{label}</T>
        {hint ? <T v="small" color={c.textSecondary}>{hint}</T> : null}
      </View>
      <Switch value={value} onValueChange={onChange} trackColor={{ true: c.teal, false: c.border }} accessibilityLabel={label} />
    </View>
  );
}

export function EmptyState({ icon, title, hint, action }: { icon: IconName; title: string; hint?: string; action?: ReactNode }) {
  const { c } = useApp();
  return (
    <View style={{ alignItems: 'center', paddingVertical: space.xl, gap: space.s }} accessible accessibilityLabel={`${title}. ${hint ?? ''}`}>
      <View style={{ width: 72, height: 72, borderRadius: 36, backgroundColor: c.cardAlt, alignItems: 'center', justifyContent: 'center' }}>
        <Ionicons name={icon} size={34} color={c.teal} />
      </View>
      <T v="h3" style={{ textAlign: 'center' }}>{title}</T>
      {hint ? <T v="small" color={c.textSecondary} style={{ textAlign: 'center', maxWidth: 300 }}>{hint}</T> : null}
      {action}
    </View>
  );
}

export function ErrorBanner({ message, onRetry, retryLabel }: { message: string; onRetry?: () => void; retryLabel?: string }) {
  const { c } = useApp();
  return (
    <Card accent={c.red} style={{ flexDirection: 'row', alignItems: 'center', gap: space.s }}>
      <Ionicons name="cloud-offline" size={22} color={c.red} accessibilityElementsHidden />
      <T style={{ flex: 1 }} v="small">{message}</T>
      {onRetry ? <Button title={retryLabel ?? 'Retry'} variant="ghost" onPress={onRetry} style={{ minHeight: 40, paddingHorizontal: space.s }} /> : null}
    </Card>
  );
}

export function Collapsible({ title, children, icon = 'information-circle' }: { title: string; children: ReactNode; icon?: IconName }) {
  const { c } = useApp();
  const [open, setOpen] = useState(false);
  return (
    <Card>
      <Pressable
        onPress={() => setOpen((o) => !o)}
        accessibilityRole="button"
        accessibilityState={{ expanded: open }}
        style={{ flexDirection: 'row', alignItems: 'center', gap: space.s, minHeight: touch - 8 }}
      >
        <Ionicons name={icon} size={20} color={c.blue} />
        <T v="h3" style={{ flex: 1 }}>{title}</T>
        <Ionicons name={open ? 'chevron-up' : 'chevron-down'} size={20} color={c.textSecondary} />
      </Pressable>
      {open ? <View style={{ gap: space.s }}>{children}</View> : null}
    </Card>
  );
}

export function Logo({ size = 44 }: { size?: number }) {
  const { c } = useApp();
  return (
    <Svg width={size} height={size} viewBox="0 0 48 48" accessibilityLabel="Qorgau AI">
      <Defs>
        <LinearGradient id="lg" x1="0" y1="0" x2="1" y2="1">
          <Stop offset="0" stopColor={c.gradient[0]} />
          <Stop offset="1" stopColor={c.gradient[1]} />
        </LinearGradient>
      </Defs>
      <Path d="M24 3 L41 9.5 V22 C41 33 33.5 41.5 24 45 C14.5 41.5 7 33 7 22 V9.5 Z" fill="url(#lg)" />
      <Path d="M16 24.5 L21.5 30 L32.5 18.5" stroke={c.onAccent} strokeWidth={3.6} strokeLinecap="round" strokeLinejoin="round" fill="none" />
    </Svg>
  );
}

const styles = StyleSheet.create({
  button: {
    minHeight: touch + 4,
    borderRadius: radius.m,
    paddingHorizontal: space.m,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: space.s,
    borderWidth: 1,
  },
});
