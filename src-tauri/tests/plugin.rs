#[test]
fn test_echo_plugin() {
    use caret_lib::plugins::caret_plugin::{CaretPlugin, EchoPlugin};
    let plugin = EchoPlugin;
    let input = "Hello, Caret!";
    let output = plugin.run(input);
    assert_eq!(output, input);
}
