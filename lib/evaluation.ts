import type {Column} from './types';
const outcomeWords=/(^|[._\s-])(conver(?:t|sion)\w*|qualif\w*|status|outcome|result|dropoff|appointment|followup|disposition)([._\s-]|$)/i;
export function eligibleEvaluationFeature(column:Column,targetKey:string):boolean {
  const name=column.name.replace(/([A-Z]+)([A-Z][a-z])/g,'$1_$2').replace(/([a-z0-9])([A-Z])/g,'$1_$2');
  return column.key!==targetKey&&column.queryable&&!column.sensitive&&['category','boolean'].includes(column.type)&&column.distinctCount<=100&&!outcomeWords.test(name);
}
