def test_celer_configuration():
    """Test the Celery application configuration.
    """
    from core.celery import app
    assert app
    broker_transport_options = app.conf.broker_transport_options
    assert broker_transport_options
    assert broker_transport_options['heartbeat'] == 0
    assert broker_transport_options['confirm_publish'] == True
    assert broker_transport_options['connect_timeout'] == 2
