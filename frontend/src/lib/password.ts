export const PASSWORD_RULE_MESSAGE = 'Use at least 8 characters with a letter and a number.';

export function isPasswordPolicyValid(password: string): boolean {
  return password.length >= 8 && /[a-z]/i.test(password) && /\d/.test(password);
}
