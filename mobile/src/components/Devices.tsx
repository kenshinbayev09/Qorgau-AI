import Svg, { Circle, G, Path, Rect, Text as SvgText } from 'react-native-svg';

import { useApp } from '../state/AppContext';

/** Рисунок: ноутбук, планшет и телефон с открытым приложением Qorgau AI. */
export function DevicesIllustration({ width = 340 }: { width?: number }) {
  const { c } = useApp();
  const h = width * 0.72;
  return (
    <Svg width={width} height={h} viewBox="0 0 340 245" accessibilityLabel="Qorgau AI на телефоне, планшете и ноутбуке">
      <Circle cx="170" cy="122" r="112" fill={c.cardAlt} />

      {/* ноутбук */}
      <G>
        <Rect x="58" y="62" width="176" height="112" rx="10" fill={c.card} stroke={c.border} strokeWidth="2" />
        <Rect x="68" y="72" width="156" height="92" rx="6" fill={c.bg} />
        <Path d="M40 180 H252 L244 192 H48 Z" fill={c.border} />
        <Rect x="122" y="180" width="48" height="5" rx="2" fill={c.textSecondary} />
        <Path d="M132 100 L146 105 V117 C146 126 140 132 132 136 C124 132 118 126 118 117 V105 Z" fill={c.teal} />
        <SvgText x="156" y="122" fill={c.text} fontSize="13" fontWeight="700">Qorgau AI</SvgText>
        <Rect x="90" y="142" width="120" height="5" rx="2.5" fill={c.border} />
        <Rect x="90" y="152" width="80" height="5" rx="2.5" fill={c.border} />
      </G>

      {/* планшет */}
      <G>
        <Rect x="226" y="88" width="88" height="124" rx="12" fill={c.card} stroke={c.border} strokeWidth="2" />
        <Rect x="234" y="98" width="72" height="104" rx="6" fill={c.bg} />
        <Circle cx="270" cy="206" r="2.5" fill={c.border} />
        <Path d="M262 124 L270 127 V135 C270 141 266 145 262 147 C258 145 254 141 254 135 V127 Z" fill={c.teal} />
        <Rect x="244" y="156" width="52" height="4" rx="2" fill={c.border} />
        <Rect x="248" y="166" width="44" height="4" rx="2" fill={c.border} />
      </G>

      {/* телефон */}
      <G>
        <Rect x="24" y="110" width="66" height="122" rx="12" fill={c.card} stroke={c.text} strokeWidth="2" />
        <Rect x="30" y="122" width="54" height="98" rx="5" fill={c.bg} />
        <Rect x="50" y="116" width="14" height="3" rx="1.5" fill={c.border} />
        <Path d="M48 146 L55 149 V156 C55 161 52 164 48 166 C44 164 41 161 41 156 V149 Z" fill={c.teal} />
        <Rect x="36" y="176" width="38" height="4" rx="2" fill={c.border} />
        <Rect x="39" y="184" width="32" height="4" rx="2" fill={c.border} />
      </G>
    </Svg>
  );
}
