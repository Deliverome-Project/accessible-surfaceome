// Isolated development deployment: public contact reads only, no write routes.
import {handleContactSites} from './contact-sites.js';
export default {async fetch(request, env) {
 if(request.method==='OPTIONS') return new Response(null,{status:204,headers:{'Access-Control-Allow-Origin':'*','Access-Control-Allow-Methods':'GET, OPTIONS'}});
 if(request.method!=='GET') return new Response('Method not allowed',{status:405});
 if(env.RATE_LIMITER && !(await env.RATE_LIMITER.limit({key:request.headers.get('CF-Connecting-IP')??'unknown'})).success) return new Response('Rate limited',{status:429,headers:{'Access-Control-Allow-Origin':'*'}});
 return handleContactSites(request,env,new URL(request.url).pathname.replace(/\/$/,''));
}};
