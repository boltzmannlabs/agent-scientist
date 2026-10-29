/** Activate chat only after its first visit, then preserve the mounted session
 * across dashboard navigation so switching pages never restarts a conversation. */
export function latchChatActivation(previous: boolean, isActive: boolean): boolean {
  return previous || isActive;
}
