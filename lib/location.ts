export type LocationPolicy={policy:string;latitude?:number;longitude?:number;radius?:number};
export function distanceMeters(a:number,b:number,c:number,d:number){const rad=Math.PI/180;const x=Math.sin((c-a)*rad/2)**2+Math.cos(a*rad)*Math.cos(c*rad)*Math.sin((d-b)*rad/2)**2;return 6371000*2*Math.atan2(Math.sqrt(x),Math.sqrt(1-x));}
export function validateLocation(policy:LocationPolicy,point:any,now=Date.now()){
 const has=point&&Number.isFinite(point.latitude)&&Number.isFinite(point.longitude)&&Number.isFinite(point.accuracy)&&Number.isFinite(point.timestamp)&&Math.abs(point.latitude)<=90&&Math.abs(point.longitude)<=180&&point.accuracy>=0;
 if(!has){if(policy.policy==='Location optional')return null;throw Error('Allow location access before recording mobile attendance.');}
 if(Math.abs(now-point.timestamp)>120000)throw Error('Location has expired. Please get a fresh location.');
 if(policy.policy==='Office geofence'){
 if(!Number.isFinite(policy.latitude)||!Number.isFinite(policy.longitude)||!Number.isFinite(policy.radius)||policy.radius!<=0||Math.abs(policy.latitude!)>90||Math.abs(policy.longitude!)>180)throw Error('Office location and radius must be configured in Company settings.');
 const distance=distanceMeters(policy.latitude!,policy.longitude!,point.latitude,point.longitude);
 if(distance+point.accuracy>policy.radius!)throw Error(`Location is outside the office radius or GPS accuracy is insufficient (${Math.round(distance)}m away, ±${Math.round(point.accuracy)}m).`);
 return {...point,distance:Math.round(distance)};
 }return point;
}
