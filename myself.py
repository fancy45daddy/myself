import aiohttp.web, asyncio, bs4, urllib.parse, fake_useragent, tempfile, sys, re, huggingface_hub, pathlib, builtins, zhconv, argparse, os, itertools

parser = argparse.ArgumentParser()
parser.add_argument('huggingface')

huggingface_hub.login(parser.parse_args().huggingface) #https://huggingface.co/settings/tokens
unlink = []

async def main():
    app = aiohttp.web.Application()
    app.add_routes([aiohttp.web.static('/', pathlib.Path(__file__).parent)])
    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    site = aiohttp.web.TCPSite(runner, '0.0.0.0', 8000)
    await site.start()
    async with aiohttp.ClientSession(headers={'user-agent':fake_useragent.UserAgent().chrome}) as client:
        async with client.get('https://myself-bbs.com/thread-46597-1-1.html') as episode:
            html = bs4.BeautifulSoup(await episode.text(), 'lxml')
            title = zhconv.convert(re.split('[／【]', html.find('title').string)[0].replace(' ', ''), 'zh-cn')
            for _ in itertools.islice(html.find('ul', attrs={'class', 'main_list'}).find_all('li', recursive=False), 0, None):
                async with client.ws_connect('wss://v.myself-bbs.com/ws') as ws:
                    href = urllib.parse.urlparse(_.find('a', attrs={'data-href':True}).get('data-href')).path
                    if 'play/' in href:
                        tid, vid = href.split('/')[-2:]
                        await ws.send_json({'tid':tid,'vid':vid,'id':''})
                    else: await ws.send_json({'tid':'','vid':'','id':href.split('/')[-1]})
                    video = 'https:' + (await ws.receive_json()).get('video')
                    print(video)
                    async with client.get(video, headers={'referer':'https://v.myself-bbs.com'}) as m3u8:
                        pathlib.Path(__file__).parent.joinpath('index.m3u8').write_bytes(re.sub(b'^[^#]\w+\.ts$', lambda _:b'/'.join((video.rsplit('/', 1)[0].encode(),  _.group(0))), await m3u8.content.read(), flags=re.MULTILINE))
                        with tempfile.NamedTemporaryFile(delete=False) as tmp:
                            sys.modules[__name__].unlink += tmp.name,
                            ffmpeg = await asyncio.create_subprocess_exec('ffmpeg', '-y', '-headers', 'referer:https://v.myself-bbs.com', '-protocol_whitelist', 'pipe,https,tls,tcp,http', '-i', 'http://localhost:8000/index.m3u8', '-f', 'mp4', tmp.name)
                            await ffmpeg.wait()
                            api = huggingface_hub.HfApi()
                            future = api.upload_file(path_or_fileobj=tmp.name, path_in_repo='/'.join(('cartoon', title, _.find('a', attrs={'href':'javascript:;'}).string.split()[1] + '.mp4')), repo_id='chaowenguo/video', repo_type='model', run_as_future=True)
    return future

asyncio.run(main()).result()
for _ in unlink: os.unlink(_)
