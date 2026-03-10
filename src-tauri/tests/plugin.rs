#[test]
fn test_echo_plugin() {
    use oxy_lib::plugins::oxy_plugin::{EchoPlugin, OxyPlugin};
    let plugin = EchoPlugin;
    let input = "Hello, Oxy!";
    let output = plugin.run(input);
    assert_eq!(output, input);
}
