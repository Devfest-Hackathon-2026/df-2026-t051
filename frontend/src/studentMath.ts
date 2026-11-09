export type Category = {label:string|null;value:number|null};
export function extrema(categories:Category[]) {
  const known=categories.filter((c):c is Category & {value:number}=>c.value!==null&&Number.isFinite(c.value));
  if(!known.length)return null;
  const min=Math.min(...known.map(c=>c.value));
  const max=Math.max(...known.map(c=>c.value));
  return {min,max,minLabels:known.filter(c=>c.value===min).map(c=>c.label),maxLabels:known.filter(c=>c.value===max).map(c=>c.label),excluded:categories.length-known.length};
}
export function difference(categories:Category[],left:number,right:number) {
  if(left===right)return null;
  const a=categories[left]?.value,b=categories[right]?.value;
  if(a===null||b===null||!Number.isFinite(a)||!Number.isFinite(b))return null;
  // Subtract the decimal representations exactly before converting to a finite
  // display number. This avoids 0.3 - 0.2 becoming 0.09999999999999998.
  function decimal(value:number):[bigint,number] {
    const [mantissa,exponent='0']=value.toString().split('e');
    return [BigInt(mantissa.replace('.','')),Number(exponent)-(mantissa.split('.')[1]?.length??0)];
  }
  const [ai,ae]=decimal(a!),[bi,be]=decimal(b!);
  const exponent=Math.min(ae,be);
  const integer=ai*10n**BigInt(ae-exponent)-bi*10n**BigInt(be-exponent);
  const result=Number(`${integer}e${exponent}`);
  if(!Number.isFinite(result))return null;
  const [rounded,roundedExponent]=decimal(result);
  const common=Math.min(exponent,roundedExponent);
  // Refuse a silently rounded result when converting back to a JS number.
  if(integer*10n**BigInt(exponent-common)!==rounded*10n**BigInt(roundedExponent-common))return null;
  return result;
}
export function formatNumber(value:number) {
  return new Intl.NumberFormat('ja-JP',{maximumSignificantDigits:21}).format(value);
}
