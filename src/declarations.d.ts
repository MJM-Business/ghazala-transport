declare module 'bwip-js' {
  const bwipjs: {
    toSVG: (opts: any) => string;
    toBuffer: (opts: any, cb?: (err: any, png: Buffer) => void) => Promise<Buffer> | void;
    [key: string]: any;
  };
  export default bwipjs;
}
