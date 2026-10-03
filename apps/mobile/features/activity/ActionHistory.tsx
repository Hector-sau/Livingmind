import { useEffect, useRef, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import type { LivingMindApi } from '../../services';
import type { ActionExecution, RequestContext } from '../../services/types';
import { colors, font, space } from '../../theme/tokens';
import { formatTime } from '../../utils/format';
import { actionStatus, mergeReceipt, scopedActions } from './actionHistoryRules';
import { formatValue } from '../devices/control';

/** Read-only evidence. No path here can confirm a plan, undo, or resend a command. */
export function ActionHistory({ api, context, refreshKey }: {
  api: LivingMindApi; context: RequestContext; refreshKey: string | null;
}) {
  const [items, setItems] = useState<ActionExecution[]>([]);
  const [note, setNote] = useState<string | null>(null);
  const [checking, setChecking] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  const generation = useRef(0);
  const key = `${context.accountId}/${context.personId}/${context.spaceId}`;
  // Do not display another person's rows during the render before the effect runs.
  const currentKey = useRef(key);
  if (currentKey.current !== key) { currentKey.current = key; generation.current += 1; }

  useEffect(() => {
    const id = ++generation.current;
    setItems([]); setNote(null); setChecking(null);
    api.getActions(context).then((rows) => {
      if (generation.current === id) setItems(scopedActions(rows, context));
    }).catch(() => {
      if (generation.current === id) setNote('操作记录暂时无法读取，没有重发设备动作。');
    });
    return () => { generation.current += 1; };
  }, [api, key, refreshKey, version]);

  const check = async (actionId: string) => {
    const id = generation.current;
    setChecking(actionId); setNote(null);
    try {
      const receipt = await api.reconcileAction(actionId, context);
      if (generation.current !== id) return;
      if (receipt.actionId !== actionId || scopedActions([receipt], context).length !== 1) throw new Error('invalid receipt');
      setItems((rows) => mergeReceipt(rows, receipt));
      setNote(receipt.status === 'unknown' ? '仍未取得可靠回执，保留未知状态；没有重发。' : '已核对原动作回执；没有重发，也没有重启服务。');
    } catch {
      if (generation.current === id) setNote('暂时无法核对，保留原结果；没有重发设备动作。');
    } finally {
      if (generation.current === id) setChecking(null);
    }
  };

  return <Card title="操作记录与结果核对" icon="document-text-outline">
    <Text style={styles.hint}>{api.mode === 'mock' ? '前端模拟没有持久化回执；请连接后端体验故障核对。'
      : '仅显示当前人物的最近操作。核对只查原回执，不重发指令；历史完成不代表设备当前仍是该数值。'}</Text>
    <Button label="刷新操作记录" variant="secondary" onPress={() => setVersion((v) => v + 1)} testID="actions-refresh" />
    {note ? <Text style={styles.hint} testID="actions-note">{note}</Text> : null}
    {scopedActions(items, context).map((item) => <View key={item.actionId} style={styles.row} testID={`action-row-${item.actionId}`}>
      <Text style={styles.title}>{({ plan: '服务计划', manual: '手动控制', undo: '撤销操作' })[item.source ?? 'plan']} · {({ light: '灯光', ac: '空调', curtain: '窗帘' })[item.device]} → {formatValue(item.device, item.requestedValue)}</Text>
      <Text style={styles.text}>{actionStatus(item)}</Text>
      <Text style={styles.hint}>{formatTime(item.requestedAt)} · {item.actionId}</Text>
      {item.lastCheckedAt ? <Text style={styles.hint}>上次核对：{formatTime(item.lastCheckedAt)}</Text> : null}
      {item.status === 'unknown' ? <>
        <Text style={styles.hint}>自动核对尝试：{item.recoveryAttempts ?? 0} 次{item.nextCheckAt ? ` · 下次：${formatTime(item.nextCheckAt)}` : ''}</Text>
        {item.recoveryExhausted ? <Text style={styles.hint}>请检查设备或网关；需要继续操作时，先确认当前状态。</Text> : null}
        <Button label="核对原动作（不重发）" variant="secondary" loading={checking === item.actionId}
          disabled={checking !== null} onPress={() => void check(item.actionId)} testID={`action-check-${item.actionId}`} />
      </> : null}
    </View>)}
  </Card>;
}

const styles = StyleSheet.create({
  hint: { color: colors.muted, fontSize: font.caption },
  title: { color: colors.ink, fontSize: font.body, fontWeight: '600' },
  text: { color: colors.ink, fontSize: font.small },
  row: { gap: space.sm, paddingVertical: space.sm, borderTopWidth: 1, borderTopColor: colors.skyLight },
});
