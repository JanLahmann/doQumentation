// Python sources are bundled as strings (plugins/python-source).
declare module '*.py' {
  const source: string;
  export default source;
}
