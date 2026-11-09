import {test,expect} from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

test('bounded public browser timings with disposable accounts',async({browser,request})=>{
  test.setTimeout(300000);
  const users=JSON.parse(process.env.CHARTBRIDGE_TEST_USERS!);
  const out=process.env.CHARTBRIDGE_AUDIT_DIR!;
  const url=process.env.CHARTBRIDGE_LIVE_URL!;
  const id='6e24c58117ad4a6e88d610b9b09bb47c';
  const result:any={student:[],comparison:[],analysis:[],mixed:[],errors:[],cloudRequests:0,studentAnalyzeRequests:0};
  function observe(page:any,student=false){const metrics={requests:0};page.on('request',(r:any)=>{if(r.url().startsWith(url)){metrics.requests++;result.cloudRequests++;if(student&&new URL(r.url()).pathname==='/api/analyze')result.studentAnalyzeRequests++;if(result.cloudRequests>120)throw Error('Bounded browser request cap exceeded');}});return metrics;}
  const contexts:any[]=[];
  try{
    await Promise.all([0,1,2].map(async index=>{
      const context=await browser.newContext({baseURL:url});contexts.push(context);const page=await context.newPage();const metrics=observe(page,true);
      const start=performance.now();await page.goto(`/learn/${id}`);await expect(page.getByRole('table')).toBeVisible();
      result.student.push({index,elapsed_ms:performance.now()-start,success:true});
      await page.getByRole('combobox',{name:'比較する項目',exact:true}).selectOption('1');await page.getByRole('combobox',{name:'差し引く項目',exact:true}).selectOption('0');
      for(let i=0;i<3;i++){
        const old=await page.getByRole('status').locator('span').elementHandle();const before=metrics.requests;const t=performance.now();
        await page.getByRole('button',{name:'数値を比較する'}).click();await page.waitForFunction(el=>!el!.isConnected,old);await expect(page.getByRole('status')).toContainText('差は 6');
        await page.evaluate(()=>new Promise<void>(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve()))));
        result.comparison.push({index,round:i,elapsed_ms:performance.now()-t,success:true,own_server_requests:metrics.requests-before});expect(metrics.requests-before).toBe(0);
      }
    }));
    expect(result.studentAnalyzeRequests).toBe(0);
    result.errors.push({kind:'actual_401',status:(await request.get('/api/me')).status()});expect(result.errors.at(-1).status).toBe(401);
    result.errors.push({kind:'actual_403',status:(await request.post('/api/drafts/'+'a'.repeat(32)+'/approve',{headers:{Authorization:`Bearer ${users.student.token}`},data:{expected_version:1,confirmed:true}})).status()});expect(result.errors.at(-1).status).toBe(403);
    const fixtures=['../backend/tests/fixtures/sample.png','../.tmp/final-audit/jp-crops/JP-H06-v2.png','../backend/tests/fixtures/sample.jpg','../.tmp/final-audit/jp-crops/JP-P02-v2.png'];
    const pages:any[]=[];
    for(let i=0;i<4;i++){
      const context=await browser.newContext({baseURL:url});contexts.push(context);const page=await context.newPage();observe(page);
      await page.goto('/');const user=i<2?users.teacherA:users.teacherB;
      await page.getByLabel('メールアドレス').fill(user.email);await page.getByLabel('パスワード',{exact:true}).fill(user.password);await page.getByRole('button',{name:'ログイン',exact:true}).click();
      await expect(page.getByText(`ログイン済み：${user.email}`,{exact:false})).toBeVisible();pages.push(page);
    }
    // Start early in a minute so a third request can verify quota without
    // risking a new generation after the fixed minute bucket rolls over.
    const seconds=(Date.now()%60000)/1000;if(seconds>7)await new Promise(r=>setTimeout(r,61000-Date.now()%60000));
    let firstStart=0;
    async function analyze(i:number){
      const page=pages[i];const start=performance.now();const row:any={index:i,fixture:path.basename(fixtures[i]),started_at:new Date().toISOString()};
      try{
        await page.locator('#chart-file').setInputFiles(fixtures[i]);const apiStart=performance.now();if(i===0)firstStart=Date.now();
        const pending=page.waitForResponse((r:any)=>r.url().endsWith('/api/analyze'),{timeout:65000});await page.getByRole('button',{name:'グラフを読み取る'}).click();
        const response=await pending;row.status=response.status();row.api_ms=performance.now()-apiStart;
        if(response.status()===200){
          const data=await response.json();expect(data.source).toBe('gemini');await expect(page.getByRole('table').first()).toBeVisible();
          await expect(page.getByRole('heading',{name:'読み取り結果',exact:true})).toBeFocused();
          row.success=true;row.unknowns=data.extraction.categories.filter((x:any)=>x.value===null).length;row.image_id=data.image_id;row.categories=data.extraction.categories.length;
          if(i===3)expect(row.unknowns).toBeGreaterThan(0);
        }else{row.success=false;await expect(page.getByRole('alert')).toBeFocused();}
      }catch(e){row.success=false;row.error_type=e instanceof Error?e.name:'unknown';}
      row.selection_to_render_ms=performance.now()-start;result.analysis.push(row);
    }
    for(const wave of [[0,1],[2,3]]){
      const pending=wave.map(analyze);
      await new Promise(r=>setTimeout(r,400));const t=performance.now();const response=await request.get('/api/materials/'+id,{timeout:30000});
      result.mixed.push({wave:wave[0]/2,status:response.status(),elapsed_ms:performance.now()-t});
      await Promise.all(pending);
      if(wave[0]===0){
        if(result.analysis.filter((x:any)=>x.index<2).every((x:any)=>x.success)&&Math.floor(firstStart/60000)===Math.floor(Date.now()/60000)){
          const r=await request.post('/api/analyze',{headers:{Authorization:`Bearer ${users.teacherA.token}`},multipart:{file:{name:'sample.png',mimeType:'image/png',buffer:fs.readFileSync(fixtures[0])}},timeout:65000});
          result.errors.push({kind:'actual_quota_429',status:r.status(),retry_after:r.headers()['retry-after']});expect(r.status()).toBe(429);
        }else result.errors.push({kind:'actual_quota_429',skipped:'minute bucket rolled over or prior analysis failed; no extra request issued'});
      }
    }
    expect(result.analysis).toHaveLength(4);expect(result.analysis.every((x:any)=>x.success)).toBe(true);
  }finally{
    fs.mkdirSync(out,{recursive:true});fs.writeFileSync(path.join(out,'browser-performance.json'),JSON.stringify(result,null,2));
    await Promise.all(contexts.map(c=>c.close()));
  }
});
