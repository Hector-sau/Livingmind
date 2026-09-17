import { Ionicons, MaterialCommunityIcons } from '@expo/vector-icons';
import type { ComponentProps } from 'react';

export type IconName = ComponentProps<typeof Ionicons>['name'];

export function Icon({ name, size = 20, color }: { name: IconName; size?: number; color: string }) {
  return <Ionicons name={name} size={size} color={color} />;
}

export type DeviceKind = 'light' | 'ac' | 'curtain';

/** Device glyphs. Curtains come from MaterialCommunityIcons (Ionicons has none). */
export function DeviceIcon({ device, size = 20, color }: { device: DeviceKind; size?: number; color: string }) {
  if (device === 'light') return <Ionicons name="bulb-outline" size={size} color={color} />;
  if (device === 'ac') return <Ionicons name="thermometer-outline" size={size} color={color} />;
  return <MaterialCommunityIcons name="curtains" size={size} color={color} />;
}
